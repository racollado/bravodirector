"""
Show Controller — the central orchestration engine.

Responsibilities:
  - Owns the show state machine (IDLE → RUNNING → PAUSED → WAITING_FOR_AI → etc.)
  - Runs a background asyncio event loop for async operations
  - Receives transcript callbacks and routes them to CueDetector
  - Executes step actions when cues fire
  - Manages voice-gated captions (two-phase: silence detection → voice onset)
  - Handles show lifecycle: start, stop, pause, skip, go_back, reset
  - Broadcasts state to WebSocket clients via callback
"""

import asyncio
import logging
import os
import re
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional

from engine.script_manager import ScriptManager, StepData
from engine.task_manager import TaskManager, TaskStatus

logger = logging.getLogger(__name__)


class ShowState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_AI = "waiting_for_ai"
    ERROR = "error"


class ShowController:
    def __init__(
        self,
        script_manager: ScriptManager,
        cue_detector,
        speech_monitor,
        audio_engine,
        osc_client,
        handlers: dict[str, Any],
        on_state_change: Optional[Callable] = None,
    ):
        self.script = script_manager
        self.cue_detector = cue_detector
        self.speech = speech_monitor
        self.audio = audio_engine
        self.osc = osc_client
        self.handlers = handlers
        self.tasks = TaskManager()

        self.state = ShowState.IDLE
        self.failure_count = 0

        # Live transcript for performer view
        self.transcript_lines: list[str] = []
        self.current_partial: str = ""

        # Voice-gated caption state
        self._voice_pending_step: Optional[StepData] = None

        # Timer state
        self._active_timer_task: Optional[asyncio.Task] = None
        self._timer_remaining: float = 0
        self._timer_total: float = 0
        # While True, speech cue matching is suppressed (start_timer countdown, silent timer delay, timed_sequence)
        self._silent_timer_delay_active: bool = False
        self._timed_sequence_active: bool = False

        # Loading state for performer view
        self._loading_message: str = ""

        # Failure display clear timer
        self._failure_clear_task: Optional[asyncio.Task] = None

        # Execution epoch — incremented on every lifecycle change (start, stop,
        # skip, go_back, reset).  Coroutines capture this value at launch and
        # bail out when it no longer matches, preventing stale coroutines from
        # continuing after the user changes the show state.
        self._epoch: int = 0

        # External callback for state broadcasts
        self._on_state_change = on_state_change
        self._last_mic_broadcast = 0.0

        # Background asyncio event loop
        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._loop_thread.start()

        self._setup_callbacks()
        logger.info("ShowController initialized")

    # ------------------------------------------------------------------
    # Event loop
    # ------------------------------------------------------------------

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _schedule(self, coro) -> asyncio.Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def _next_epoch(self) -> int:
        self._epoch += 1
        return self._epoch

    def _epoch_valid(self, epoch: int) -> bool:
        return self._epoch == epoch

    @staticmethod
    def _step_should_chain_execute(step: Optional[StepData]) -> bool:
        """Steps that run immediately when advanced to (no speech cue)."""
        if not step:
            return False
        t = step.trigger.get("type")
        if t == "timer":
            return True
        return t == "auto" and not step.trigger.get("wait_for_voice")

    async def _silent_timer_delay(self, duration: float, epoch: int):
        """Background wait for timer-trigger steps only: no OSC, no on-screen countdown."""
        if duration <= 0:
            return
        self._silent_timer_delay_active = True
        try:
            remaining = float(duration)
            while remaining > 0 and self._epoch_valid(epoch):
                if self.state == ShowState.PAUSED:
                    while self.state == ShowState.PAUSED:
                        await asyncio.sleep(0.1)
                        if not self._epoch_valid(epoch):
                            return
                chunk = min(0.25, remaining)
                await asyncio.sleep(chunk)
                remaining -= chunk
        finally:
            self._silent_timer_delay_active = False

    def _suppress_cue_matching(self) -> bool:
        """Skip cue detection during visible/hidden timer waits and timed_sequence playback."""
        if self._timer_remaining > 0:
            return True
        if self._silent_timer_delay_active:
            return True
        if self._timed_sequence_active:
            return True
        return False

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _setup_callbacks(self):
        if self.speech:
            self.speech.set_transcript_callback(self._on_transcript)
            if hasattr(self.speech, "set_level_callback"):
                self.speech.set_level_callback(self._on_mic_level)
        if self.cue_detector:
            self.cue_detector.set_cue_callback(self._on_cue_detected)

    def _on_mic_level(self, _level: float):
        now = time.monotonic()
        if now - self._last_mic_broadcast < 0.05:
            return
        self._last_mic_broadcast = now
        self._broadcast_state()

    def _on_transcript(self, text: str, is_final: bool):
        if is_final and text.strip():
            self.transcript_lines.append(text.strip())
            if len(self.transcript_lines) > 50:
                self.transcript_lines = self.transcript_lines[-50:]
            self.current_partial = ""
        elif text.strip():
            self.current_partial = text.strip()

        

        if self.cue_detector and not self._suppress_cue_matching():
            self.cue_detector.process_transcript(text, is_final)

        self._broadcast_state()

    def _on_voice_detected(self):
        step = self._voice_pending_step
        if not step:
            return
        self._voice_pending_step = None
        if step.caption:
            self._display_step_caption(step)
            logger.info("Voice detected — caption shown for step '%s'", step.id)
        self._broadcast_state()

    def _on_cue_detected(self, step_index: int, phrase: str, confidence: float):
        if self.state not in (ShowState.RUNNING, ShowState.WAITING_FOR_AI):
            return
        logger.info("CUE DETECTED: index=%d phrase='%s' conf=%.2f", step_index, phrase, confidence)
        already_here = self.script.current_index == step_index
        epoch = self._next_epoch()
        self._voice_pending_step = None
        if self.audio and hasattr(self.audio, "cancel_voice_wait"):
            self.audio.cancel_voice_wait()
        self.script.set_index(step_index)
        if not already_here:
            self._send_caption_for_step(self.script.current_step)
        self._schedule(self._execute_step(step_index, epoch))

    # ------------------------------------------------------------------
    # Show lifecycle
    # ------------------------------------------------------------------

    def start_show(self, start_index: int = 0):
        if self.state != ShowState.IDLE:
            return
        total = self.script.total_steps
        if total <= 0:
            logger.warning("Cannot start: script has no steps")
            return
        try:
            idx = int(start_index)
        except (TypeError, ValueError):
            idx = 0
        idx = max(0, min(idx, total - 1))
        logger.info("STARTING SHOW from step index %d", idx)
        epoch = self._next_epoch()
        self.script.set_index(idx)
        self.state = ShowState.RUNNING
        self._schedule(self._start_show_sequence(epoch))
        self._broadcast_state()

    async def _start_show_sequence(self, epoch: int):
        while self._epoch_valid(epoch):
            current = self.script.current_step
            if current and self._step_should_chain_execute(current):
                await self._execute_step(current.index, epoch)
            else:
                break

        if not self._epoch_valid(epoch):
            return

        # Align linear cue queue with current position (required when start_show used a
        # non-zero start_index; otherwise _next_cue_idx still points at the first cue).
        self._reregister_cues()

        current = self.script.current_step
        if current:
            self._send_caption_for_step(current)

        if self.speech:
            self.speech.start()
            logger.info("Speech monitoring started")
        self._broadcast_state()

    def stop_show(self):
        logger.info("STOPPING SHOW")
        self._next_epoch()
        self.state = ShowState.IDLE
        self._voice_pending_step = None
        if self.audio and hasattr(self.audio, "cancel_voice_wait"):
            self.audio.cancel_voice_wait()
        self._loading_message = ""
        if self.speech:
            self.speech.stop()
        self.tasks.cancel_all()
        self.audio.stop_all()
        self._broadcast_state()

    def pause_show(self):
        if self.state == ShowState.PAUSED:
            logger.info("RESUMING SHOW")
            self.state = ShowState.RUNNING
            if self.speech:
                self.speech.resume()
            self.audio.resume_all()
            self.osc.send_resume()
            current = self.script.current_step
            if current:
                self._send_caption_for_step(current)
        else:
            logger.info("PAUSING SHOW")
            self.state = ShowState.PAUSED
            if self.speech:
                self.speech.pause()
            self.audio.pause_all()
            self.osc.send_pause()
            self.osc.send_caption("[OFFSCRIPT]", "#ff0000")
        self._broadcast_state()

    def add_failure(self):
        """Increment failure counter, play SFX, send OSC — without skipping."""
        logger.info("ADD FAILURE (no skip)")
        self.failure_count += 1
        sfx = self.script.settings.get("failure", {}).get("sfx")
        if sfx:
            self.audio.play("sfx", sfx, loop=False)

        self.osc.send("/failure", f"Failure count: {self.failure_count}")
        if self._failure_clear_task and not self._failure_clear_task.done():
            self._failure_clear_task.cancel()
        self._failure_clear_task = asyncio.run_coroutine_threadsafe(
            self._clear_failure_after(2.0), self._loop
        )
        self._broadcast_state()

    def skip_with_failure(self):
        logger.info("SKIP WITH FAILURE")
        self.add_failure()
        self._do_skip()

    async def _clear_failure_after(self, delay: float):
        await asyncio.sleep(delay)
        self.osc.send("/failure", "")

    def skip_clean(self):
        logger.info("SKIP CLEAN")
        self._do_skip()

    def _do_skip(self):
        epoch = self._next_epoch()
        self._voice_pending_step = None
        if self.audio and hasattr(self.audio, "cancel_voice_wait"):
            self.audio.cancel_voice_wait()
        self.audio.stop_layer("main")

        current = self.script.current_step
        if current and self.cue_detector:
            self.cue_detector.mark_step_triggered(current.index)

        next_step = self.script.advance()
        if not next_step:
            return
        self._send_caption_for_step(next_step)
        self._ensure_speech()
        if self._step_should_chain_execute(next_step):
            self._schedule(self._execute_step(next_step.index, epoch))
        self._broadcast_state()

    def go_back(self):
        logger.info("GO BACK")
        self._next_epoch()
        self._voice_pending_step = None
        if self.audio and hasattr(self.audio, "cancel_voice_wait"):
            self.audio.cancel_voice_wait()
        self.audio.stop_layer("main")
        step = self.script.go_back()
        if step:
            self._reregister_cues()
            self._send_caption_for_step(step)
        self._ensure_speech()
        self._broadcast_state()

    def reset_show(self):
        logger.info("RESETTING SHOW")
        self.stop_show()
        self.script.reset()
        self._reregister_cues()
        self.failure_count = 0
        self.transcript_lines.clear()
        self.current_partial = ""
        self.tasks.clear()
        self._timer_remaining = 0
        self._timer_total = 0
        if self._failure_clear_task and not self._failure_clear_task.done():
            self._failure_clear_task.cancel()
        self.osc.send("/failure", "")
        self.state = ShowState.IDLE
        self._broadcast_state()

    def _reregister_cues(self):
        """Rebuild cue list, marking cues for steps before the current one
        as triggered so the detector resumes from the right position."""
        if self.cue_detector:
            self.cue_detector.clear_all_cues()
            current_idx = self.script.current_index
            for cue in self.script.get_all_cue_phrases():
                self.cue_detector.add_cue(
                    phrase=cue["phrase"],
                    step_index=cue["step_index"],
                    confidence_threshold=cue["confidence"],
                )
                if cue["step_index"] < current_idx:
                    self.cue_detector.mark_step_triggered(cue["step_index"])

    # ------------------------------------------------------------------
    # Caption dispatch
    # ------------------------------------------------------------------

    def _resolve_caption_dict(self, caption: dict) -> dict:
        """Resolve $task refs and text_append_task for runtime caption text."""
        cap = dict(caption)
        tat = cap.pop("text_append_task", None)
        if tat:
            base = cap.get("text") or cap.get("text_source") or ""
            if isinstance(base, str) and base.startswith("$"):
                resolved = self.tasks.resolve_reference(base)
                base = "" if resolved is None else str(resolved)
            append_data = self.tasks.get_output(tat)
            if append_data:
                cap["text"] = str(base) + str(append_data)
        else:
            text = cap.get("text", "")
            if isinstance(text, str) and text.startswith("$"):
                resolved = self.tasks.resolve_reference(text)
                if resolved is not None:
                    cap["text"] = str(resolved)
            elif cap.get("text_source"):
                ts = cap["text_source"]
                if isinstance(ts, str) and ts.startswith("$"):
                    resolved = self.tasks.resolve_reference(ts)
                    if resolved is not None:
                        cap["text"] = str(resolved)
        return cap

    def _display_step_caption(self, step: StepData):
        if not step.caption or not step.caption.get("display", True):
            return
        resolved = self._resolve_caption_dict(step.caption)
        self.handlers["caption"].display(step, caption_override=resolved)

    def _send_caption_for_step(self, step: StepData):
        if not step:
            return

        if step.trigger.get("wait_for_voice"):
            self._voice_pending_step = step
            delay = float(step.trigger.get("delay", 0))
            logger.info(
                "Voice-gated step '%s': previous caption holds %.1fs then clears",
                step.id, delay,
            )
            self._schedule(self._voice_gate_sequence(step, delay, self._epoch))
            return

        if step.caption and step.caption.get("display", True):
            self._display_step_caption(step)

    async def _voice_gate_sequence(self, step: StepData, delay: float, epoch: int):
        """Hold previous caption for `delay` seconds, clear, wait for voice, then show."""
        if delay > 0:
            await asyncio.sleep(delay)
        if not self._epoch_valid(epoch):
            return
        self.handlers["caption"].clear()
        logger.info("Caption cleared — arming voice onset for '%s'", step.id)
        self._broadcast_state()
        if self.audio and hasattr(self.audio, "wait_for_voice"):
            try:
                self.audio.wait_for_voice(callback=self._on_voice_detected, threshold=0.01)
            except RuntimeError:
                logger.warning("Could not start voice monitor (interpreter shutting down)")

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    async def _execute_step(self, step_index: int, epoch: int):
        if not self._epoch_valid(epoch):
            return
        step = self.script.get_step(step_index)
        if not step:
            return

        logger.info("Executing step '%s' (index %d)", step.id, step_index)

        if step.caption and step.caption.get("display", True):
            self._display_step_caption(step)

        for overlay in step.overlays:
            self._handle_overlay(overlay)

        if step.mode == "timed_sequence":
            await self._execute_timed_sequence(step, epoch)
            if self._epoch_valid(epoch):
                await self._advance_after_step(step_index, epoch)
            return

        delay = step.trigger.get("delay", 0)
        if delay and delay > 0:
            await asyncio.sleep(delay)
            if not self._epoch_valid(epoch):
                return

        if step.trigger.get("type") == "timer":
            td = float(step.trigger.get("duration", 0))
            if td > 0:
                logger.info(
                    "Timer step '%s': silent delay %.1fs before actions (no OSC / on-screen timer)",
                    step.id,
                    td,
                )
                await self._silent_timer_delay(td, epoch)
                if not self._epoch_valid(epoch):
                    return

        for action in step.actions:
            if not self._epoch_valid(epoch):
                return
            if self.state == ShowState.PAUSED:
                while self.state == ShowState.PAUSED:
                    await asyncio.sleep(0.1)
                    if not self._epoch_valid(epoch):
                        return
            await self._execute_action(action, step, epoch)

        if self._epoch_valid(epoch):
            await self._advance_after_step(step_index, epoch)

    async def _advance_after_step(self, step_index: int, epoch: int):
        if not self._epoch_valid(epoch):
            return
        current = self.script.current_step
        if not current or current.index != step_index:
            return

        next_step = self.script.advance()
        if next_step:
            self._send_caption_for_step(next_step)
            if self._step_should_chain_execute(next_step):
                await self._execute_step(next_step.index, epoch)
        self._broadcast_state()

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    async def _execute_action(self, action: dict, step: StepData, epoch: int):
        action_type = action.get("type")
        blocking = action.get("blocking", False)

        resolved = self._resolve_action_refs(action)

        try:
            if action_type == "play_audio":
                await self._act_play_audio(resolved, epoch)
            elif action_type == "play_video":
                self._act_play_video(resolved)
            elif action_type == "generate_text":
                await self._act_generate_text(resolved, step, epoch)
            elif action_type == "generate_music":
                await self._act_generate_music(resolved, blocking, epoch)
            elif action_type == "generate_sfx":
                await self._act_generate_sfx(resolved, blocking, epoch)
            elif action_type == "generate_tts":
                await self._act_generate_tts(resolved, step, epoch)
            elif action_type == "generate_video":
                await self._act_generate_video(resolved, blocking, epoch)
            elif action_type == "generate_image":
                await self._act_generate_image(resolved, blocking, epoch)
            elif action_type == "fetch_submissions":
                await self._act_fetch_submissions(resolved, epoch)
            elif action_type == "show_qr":
                self.osc.send("/qr/show", resolved.get("url", ""))
            elif action_type == "hide_qr":
                self.osc.send("/qr/hide")
            elif action_type == "start_timer":
                await self._act_timer(resolved, epoch)
            elif action_type == "audio_control":
                self._act_audio_control(resolved)
            elif action_type == "send_osc":
                self.osc.send(resolved.get("address", ""), *resolved.get("args", []))
            else:
                logger.warning("Unknown action type: %s", action_type)
        except Exception as e:
            logger.error("Action '%s' failed: %s", action_type, e)
            self.failure_count += 1
        finally:
            self._broadcast_state()

    def _resolve_action_refs(self, action: dict) -> dict:
        """Replace $task_id references with resolved outputs."""
        resolved = dict(action)
        for key in ("file", "source", "text_source"):
            val = resolved.get(key)
            if isinstance(val, str) and val.startswith("$"):
                resolved[key] = self.tasks.resolve_reference(val)
        # prompt_source: load prompt base text from a $task_id or a file path
        prompt_src = resolved.get("prompt_source")
        if prompt_src:
            if isinstance(prompt_src, str) and prompt_src.startswith("$"):
                src_text = self.tasks.resolve_reference(prompt_src) or ""
            elif isinstance(prompt_src, str) and os.path.isfile(prompt_src):
                with open(prompt_src, "r") as f:
                    src_text = f.read()
            else:
                src_text = ""
            if src_text:
                resolved["prompt"] = resolved.get("prompt", "") + "\n\n" + src_text
        if "prompt_append_task" in resolved:
            append_data = self.tasks.get_output(resolved["prompt_append_task"])
            if append_data:
                resolved["prompt"] = resolved.get("prompt", "") + f"\n\nAudience suggestions:\n{append_data}"
        if "text_append_task" in resolved:
            append_data = self.tasks.get_output(resolved["text_append_task"])
            if append_data:
                base = resolved.get("text") or resolved.get("text_source") or ""
                resolved["text"] = base + str(append_data)
        return resolved

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _act_play_audio(self, action: dict, epoch: int):
        filepath = action.get("file") or action.get("source")
        layer = action.get("layer", "main")
        loop = action.get("loop", False)
        blocking = action.get("blocking", False)

        if not filepath:
            logger.warning("play_audio: no file specified")
            return

        vol = float(action.get("volume", 1.0))
        self.audio.play(layer, filepath, loop=loop, volume=vol)

        if blocking:
            while self.audio.is_playing(layer) and self._epoch_valid(epoch):
                await asyncio.sleep(0.3)

    def _act_play_video(self, action: dict):
        filepath = action.get("file") or action.get("source")
        if filepath:
            volume = float(action.get("volume", 1.0))
            self.osc.send("/media", os.path.abspath(str(filepath)), volume)
            self.osc.send("/pause", 1)

    async def _act_generate_text(self, action: dict, step: StepData, epoch: int):
        prompt = action.get("prompt", "")
        blocking = action.get("blocking", True)
        inject_cfg = action.get("inject")
        task_id = action.get("task_id", f"text_{step.id}")
        output_file = action.get("output_file")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        if blocking:
            self.state = ShowState.WAITING_FOR_AI
            self.handlers["caption"].display_raw("Generating text...", "#a78bfa")
            if loading_sfx:
                self.audio.play("sfx", loading_sfx, loop=True)
            self._broadcast_state()

        logger.info("[generate_text:%s] PROMPT:\n%s", task_id, prompt)
        try:
            generated = await self.handlers["gemini"].generate_async(prompt)
            logger.info("[generate_text:%s] OUTPUT:\n%s", task_id, generated)
            if not self._epoch_valid(epoch):
                return

            if generated:
                txt_path = output_file or f"./assets/text/{task_id}.txt"
                os.makedirs(os.path.dirname(txt_path), exist_ok=True)
                with open(txt_path, "w") as f:
                    f.write(generated)
                logger.info("Generated text saved to %s", txt_path)

            self.tasks.complete(task_id, generated)

            if inject_cfg and generated:
                mode = inject_cfg.get("mode", "per_sentence")
                color = inject_cfg.get("caption_color", "#ff4444")
                trigger = inject_cfg.get("trigger_mode", "speech")
                overlay = inject_cfg.get("overlay")

                if mode == "per_sentence":
                    sentences = self._split_sentences(generated)
                    new_steps = self.script.inject_sentences(
                        after_index=step.index,
                        sentences=sentences,
                        caption_color=color,
                        trigger_mode=trigger,
                        overlay=overlay,
                        parent_step_id=step.id,
                    )
                    self._register_injected_cues(new_steps)
                elif mode == "per_line":
                    lines = [l.strip() for l in generated.split("\n") if l.strip()]
                    new_steps = self.script.inject_lines(
                        after_index=step.index,
                        lines=lines,
                        caption_color=color,
                        trigger_mode=trigger,
                        parent_step_id=step.id,
                    )
                    self._register_injected_cues(new_steps)
        finally:
            if blocking and self._epoch_valid(epoch):
                if loading_sfx:
                    self.audio.stop_layer("sfx")
                if complete_sfx:
                    self.audio.play("sfx", complete_sfx, loop=False)
                self._loading_message = ""
                self.state = ShowState.RUNNING
                self._broadcast_state()

    async def _act_generate_music(self, action: dict, blocking: bool, epoch: int):
        task_id = action.get("task_id", "music")
        model = action.get("model", self.script.settings.get("models", {}).get("music", ""))
        prompt = action.get("prompt", "")
        duration = action.get("duration", 90)
        fallback = action.get("fallback")
        output_file = action.get("output_file")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        logger.info("[generate_music:%s] MODEL=%s PROMPT:\n%s", task_id, model, prompt)
        coro = self.handlers["replicate"].generate_music(
            model=model,
            prompt=prompt,
            duration=duration,
            fallback=fallback,
            output_file=output_file,
            action=action,
        )

        if blocking:
            self.state = ShowState.WAITING_FOR_AI
            self.handlers["caption"].display_raw("Generating music...", "#a78bfa")
            if loading_sfx:
                self.audio.play("sfx", loading_sfx, loop=True)
            self._broadcast_state()
            try:
                result = await coro
                logger.info("[generate_music:%s] OUTPUT: %s", task_id, result)
                self.tasks.complete(task_id, result)
            finally:
                if self._epoch_valid(epoch):
                    if loading_sfx:
                        self.audio.stop_layer("sfx")
                    if complete_sfx:
                        self.audio.play("sfx", complete_sfx, loop=False)
                    self._loading_message = ""
                    self.state = ShowState.RUNNING
                    self._broadcast_state()
        else:
            task = self._loop.create_task(coro)

            async def _wrap():
                try:
                    result = await task
                    logger.info("[generate_music:%s] OUTPUT: %s", task_id, result)
                    self.tasks.complete(task_id, result)
                except Exception as e:
                    logger.error("Background music generation failed: %s", e)
                    if fallback:
                        self.tasks.complete(task_id, fallback)

            self._loop.create_task(_wrap())

    async def _act_generate_sfx(self, action: dict, blocking: bool, epoch: int):
        """Text-to-SFX via Replicate (e.g. sepal/audiogen); plays the file when ready."""
        task_id = action.get("task_id", "sfx")
        model = action.get("model", self.script.settings.get("models", {}).get("sfx", "sepal/audiogen"))
        prompt = action.get("prompt", "")
        duration = action.get("duration", 3)
        fallback = action.get("fallback")
        output_file = action.get("output_file")
        layer = action.get("layer", "sfx")
        volume = float(action.get("volume", 1.0))
        play_immediately = action.get("play_immediately", True)

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        logger.info("[generate_sfx:%s] MODEL=%s PROMPT:\n%s", task_id, model, prompt)
        coro = self.handlers["replicate"].generate_sfx(
            model=model,
            prompt=prompt,
            duration=duration,
            fallback=fallback,
            output_file=output_file,
            action=action,
        )

        def _play_result(path: Optional[str]):
            if not path or not play_immediately or not self._epoch_valid(epoch):
                return
            self.audio.play(layer, path, loop=False, volume=volume)

        if blocking:
            self.state = ShowState.WAITING_FOR_AI
            self.handlers["caption"].display_raw("Generating sound effect...", "#a78bfa")
            if loading_sfx:
                self.audio.play("sfx", loading_sfx, loop=True)
            self._broadcast_state()
            result = None
            try:
                result = await coro
                logger.info("[generate_sfx:%s] OUTPUT: %s", task_id, result)
                if not self._epoch_valid(epoch):
                    return
                self.tasks.complete(task_id, result)
            finally:
                if self._epoch_valid(epoch):
                    if loading_sfx:
                        self.audio.stop_layer("sfx")
                    if complete_sfx and not (result and play_immediately):
                        self.audio.play("sfx", complete_sfx, loop=False)
                    self._loading_message = ""
                    self.state = ShowState.RUNNING
                    self._broadcast_state()
            if self._epoch_valid(epoch):
                _play_result(result)
        else:
            task = self._loop.create_task(coro)

            async def _wrap():
                try:
                    result = await task
                    logger.info("[generate_sfx:%s] OUTPUT: %s", task_id, result)
                    if not self._epoch_valid(epoch):
                        return
                    self.tasks.complete(task_id, result)
                    _play_result(result)
                except Exception as e:
                    logger.error("Background SFX generation failed: %s", e)
                    if fallback:
                        self.tasks.complete(task_id, fallback)
                        _play_result(fallback)

            self._loop.create_task(_wrap())

    async def _act_generate_tts(self, action: dict, step: StepData, epoch: int):
        task_id = action.get("task_id", f"tts_{step.id}")
        model = action.get("model", self.script.settings.get("models", {}).get("tts", ""))
        text = action.get("text") or action.get("text_source") or ""
        voice = action.get("voice", "default")
        inject_cfg = action.get("inject")
        output_file = action.get("output_file")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        logger.info("[generate_tts:%s] MODEL=%s VOICE=%s TEXT:\n%s", task_id, model, voice, text)
        self.state = ShowState.WAITING_FOR_AI
        self._loading_message = "Generating voice..."
        self.handlers["caption"].display_raw("Generating voice...", "#a78bfa")
        if loading_sfx:
            self.audio.play("sfx", loading_sfx, loop=True)
        self._broadcast_state()

        try:
            result = await self.handlers["replicate"].generate_tts(
                model=model, text=text, voice=voice, output_file=output_file, subtitle_enable=True
            )
            logger.info("[generate_tts:%s] OUTPUT: %s", task_id, result)

            if loading_sfx:
                self.audio.stop_layer("sfx")
            if complete_sfx:
                self.audio.play("sfx", complete_sfx, loop=False)
            self._loading_message = ""
            self.state = ShowState.RUNNING
            self._broadcast_state()

            if not self._epoch_valid(epoch):
                return
            self.tasks.complete(task_id, result)

            if inject_cfg and result:
                color = inject_cfg.get("caption_color", "#88ccff")
                audio_path = result.get("audio_path")
                word_timestamps = result.get("word_timestamps", [])
                injected: list[StepData] = []

                if word_timestamps:
                    injected = self.script.inject_tts_driven(
                        after_index=step.index,
                        words_with_timestamps=word_timestamps,
                        caption_color=color,
                        parent_step_id=step.id,
                    )
                    # Injected steps shift indices; cue phrase → step_index mappings must match
                    # the current script or the next speech line can jump to wrong (e.g. TTS) steps.
                    self._reregister_cues()

                if audio_path and injected:
                    import pygame
                    try:
                        snd = pygame.mixer.Sound(audio_path)
                        actual_duration = snd.get_length()
                    except Exception:
                        actual_duration = 0

                    estimated_end = word_timestamps[-1].get("end", 0) if word_timestamps else 0
                    if actual_duration > 0 and estimated_end > 0:
                        scale = actual_duration / estimated_end
                        logger.info(
                            "[generate_tts:%s] Audio duration=%.1fs, estimated=%.1fs, scale=%.3f",
                            task_id, actual_duration, estimated_end, scale,
                        )
                    else:
                        scale = 1.0

                    self.audio.play("main", audio_path, loop=False)
                    start_time = time.monotonic()
                    ts_index = 0

                    while self.audio.is_playing("main") and self._epoch_valid(epoch):
                        elapsed = time.monotonic() - start_time
                        while ts_index < len(injected) and elapsed >= word_timestamps[ts_index]["start"] * scale:
                            tts_step = injected[ts_index]
                            self.script.set_index(tts_step.index)
                            if tts_step.caption:
                                self.handlers["caption"].display(tts_step)
                            ts_index += 1
                            self._broadcast_state()
                        await asyncio.sleep(0.05)

                    if self._epoch_valid(epoch):
                        self.script.set_index(injected[-1].index)
                        self._reregister_cues()
                        await self._advance_after_step(injected[-1].index, epoch)
                elif audio_path:
                    self.audio.play("main", audio_path, loop=False)
                    while self.audio.is_playing("main") and self._epoch_valid(epoch):
                        await asyncio.sleep(0.3)
            elif result and result.get("audio_path"):
                audio_path = result["audio_path"]
                self.audio.play("main", audio_path, loop=False)
                while self.audio.is_playing("main") and self._epoch_valid(epoch):
                    await asyncio.sleep(0.3)
        except Exception:
            if loading_sfx:
                self.audio.stop_layer("sfx")
            self._loading_message = ""
            self.state = ShowState.RUNNING
            self._broadcast_state()
            raise

    async def _act_generate_video(self, action: dict, blocking: bool, epoch: int):
        task_id = action.get("task_id", "video")
        model = action.get("model", self.script.settings.get("models", {}).get("video", ""))
        prompt = action.get("prompt", "")
        duration = action.get("duration", 5)
        output_file = action.get("output_file")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        logger.info("[generate_video:%s] MODEL=%s PROMPT:\n%s", task_id, model, prompt)
        coro = self.handlers["replicate"].generate_video(
            model=model, prompt=prompt, duration=duration, output_file=output_file,
        )

        if blocking:
            self.state = ShowState.WAITING_FOR_AI
            self._loading_message = "Generating video..."
            self.handlers["caption"].display_raw("Generating video...", "#a78bfa")
            if loading_sfx:
                self.audio.play("sfx", loading_sfx, loop=True)
            self._broadcast_state()
            try:
                result = await coro
                logger.info("[generate_video:%s] OUTPUT: %s", task_id, result)
                self.tasks.complete(task_id, result)
            finally:
                if self._epoch_valid(epoch):
                    if loading_sfx:
                        self.audio.stop_layer("sfx")
                    if complete_sfx:
                        self.audio.play("sfx", complete_sfx, loop=False)
                    self._loading_message = ""
                    self.state = ShowState.RUNNING
                    self._broadcast_state()
        else:
            async def _wrap():
                try:
                    result = await coro
                    logger.info("[generate_video:%s] OUTPUT: %s", task_id, result)
                    self.tasks.complete(task_id, result)
                except Exception as e:
                    logger.error("Background video generation failed: %s", e)

            self._loop.create_task(_wrap())

    async def _act_generate_image(self, action: dict, blocking: bool, epoch: int):
        task_id = action.get("task_id", "gen_image")
        model = action.get("model", "google/imagen-4")
        prompt = action.get("prompt", "")
        aspect_ratio = action.get("aspect_ratio", "16:9")
        output_file = action.get("output_file")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        logger.info("[generate_image:%s] MODEL=%s PROMPT:\n%s", task_id, model, prompt)
        coro = self.handlers["replicate"].generate_image(
            model=model, prompt=prompt, aspect_ratio=aspect_ratio,
            output_file=output_file,
        )

        if blocking:
            self.state = ShowState.WAITING_FOR_AI
            self._loading_message = action.get("loading_message", "Generating image...")
            self.handlers["caption"].display_raw("Generating image...", "#a78bfa")
            if loading_sfx:
                self.audio.play("sfx", loading_sfx, loop=True)
            self._broadcast_state()
            try:
                result = await coro
                logger.info("[generate_image:%s] OUTPUT: %s", task_id, result)
                self.tasks.complete(task_id, result)
            finally:
                if self._epoch_valid(epoch):
                    if loading_sfx:
                        self.audio.stop_layer("sfx")
                    if complete_sfx:
                        self.audio.play("sfx", complete_sfx, loop=False)
                    self._loading_message = ""
                    self.state = ShowState.RUNNING
                    self._broadcast_state()
        else:
            async def _wrap():
                try:
                    result = await coro
                    logger.info("[generate_image:%s] OUTPUT: %s", task_id, result)
                    self.tasks.complete(task_id, result)
                except Exception as e:
                    logger.error("Background image generation failed: %s", e)

            self._loop.create_task(_wrap())

    async def _act_fetch_submissions(self, action: dict, epoch: int):
        task_id = action.get("task_id", "submissions")
        table = action.get("table")

        gen_sfx = self.script.settings.get("generation", {})
        loading_sfx = gen_sfx.get("loading_sfx")
        complete_sfx = gen_sfx.get("complete_sfx")

        self.state = ShowState.WAITING_FOR_AI
        self.handlers["caption"].display_raw("Fetching audience submissions...", "#a78bfa")
        if loading_sfx:
            self.audio.play("sfx", loading_sfx, loop=True)
        self._broadcast_state()

        try:
            handler = self.handlers.get("dynamodb")
            if handler and table:
                lyrics = await asyncio.get_running_loop().run_in_executor(
                    None, handler.fetch_all, table
                )
                compiled = handler.compile_for_prompt(lyrics)
                self.tasks.complete(task_id, compiled)
                logger.info("Fetched %d submissions from DynamoDB", len(lyrics))
            else:
                self.tasks.complete(task_id, "")
                logger.warning("DynamoDB handler not available")
        finally:
            if self._epoch_valid(epoch):
                if loading_sfx:
                    self.audio.stop_layer("sfx")
                if complete_sfx:
                    self.audio.play("sfx", complete_sfx, loop=False)
                self._loading_message = ""
                self.state = ShowState.RUNNING
                self._broadcast_state()

    async def _act_timer(self, action: dict, epoch: int):
        duration = action.get("duration", 60)
        display = action.get("display", True)
        blocking = action.get("blocking", True)

        self._timer_total = duration
        self._timer_remaining = duration

        async def _countdown():
            remaining = duration
            while remaining > 0 and self._epoch_valid(epoch):
                if self.state == ShowState.PAUSED:
                    await asyncio.sleep(0.1)
                    continue
                self._timer_remaining = remaining
                if display:
                    self.osc.send("/timer", remaining)
                self._broadcast_state()
                await asyncio.sleep(1)
                remaining -= 1
            self._timer_remaining = 0
            if display:
                self.osc.send("/timer", "")
            self._broadcast_state()

        if blocking:
            await _countdown()
        else:
            self._active_timer_task = self._loop.create_task(_countdown())

    def _act_audio_control(self, action: dict):
        layer = action.get("layer", "music")
        command = action.get("command", "")
        raw_val = action.get("value")
        duration = float(action.get("duration") or 0)
        try:
            value = float(raw_val) if raw_val is not None and raw_val != "" else None
        except (TypeError, ValueError):
            value = None

        if command == "fade_out":
            self.audio.fade_out(layer, duration)
        elif command == "fade_in":
            self.audio.fade_in(layer, duration)
        elif command == "set_volume":
            if value is None:
                logger.warning("audio_control set_volume: missing or invalid value")
                return
            self.audio.set_volume(layer, value, duration)
        elif command == "set_speed":
            mult = float(value) if value is not None else 1.0
            self.audio.set_speed(layer, mult, duration)
        elif command == "set_pitch":
            mult = float(value) if value is not None else 1.0
            self.audio.set_pitch(layer, mult, duration)
        elif command == "stop":
            self.audio.stop_layer(layer)

    # ------------------------------------------------------------------
    # Timed sequence execution
    # ------------------------------------------------------------------

    async def _execute_timed_sequence(self, step: StepData, epoch: int):
        if not step.sequence or not step.audio:
            return

        self._timed_sequence_active = True
        try:
            audio_file = step.audio.get("file")
            layer = step.audio.get("layer", "music")
            loop = step.audio.get("loop", False)

            if audio_file:
                self.audio.play(layer, audio_file, loop=loop)

            import time
            start_time = time.monotonic()

            seq = sorted(step.sequence, key=lambda s: s.get("time", 0))
            for entry in seq:
                if not self._epoch_valid(epoch):
                    return
                target = entry.get("time", 0)
                elapsed = time.monotonic() - start_time
                wait = target - elapsed
                if wait > 0:
                    await asyncio.sleep(wait)
                    if not self._epoch_valid(epoch):
                        return

                cap = entry.get("caption")
                if cap:
                    self.osc.send_caption(cap.get("text", ""), cap.get("color", "#ffffff"))
                elif cap is None:
                    self.osc.send("/caption/clear")

                video_ref = entry.get("video")
                if video_ref:
                    video_path = self.tasks.resolve_reference(video_ref) if isinstance(video_ref, str) and video_ref.startswith("$") else video_ref
                    if video_path:
                        vol = float(entry.get("volume", 1.0))
                        self.osc.send("/media", os.path.abspath(str(video_path)), vol)

                self._broadcast_state()

            if not loop:
                while self.audio.is_playing(layer) and self._epoch_valid(epoch):
                    await asyncio.sleep(0.3)
        finally:
            self._timed_sequence_active = False

    # ------------------------------------------------------------------
    # Overlay handling
    # ------------------------------------------------------------------

    def _handle_overlay(self, overlay: dict):
        otype = overlay.get("type", "")
        vol = float(overlay.get("volume", 1.0))
        if otype == "show_image":
            filepath = overlay.get("file", "")
            if filepath:
                self.osc.send("/media", os.path.abspath(filepath), vol)
        elif otype == "hide_image":
            self.osc.send("/media", os.path.abspath("./assets/image/black.png"), 0.0)
        elif otype == "play_video":
            src = overlay.get("source", overlay.get("file", ""))
            if isinstance(src, str) and src.startswith("$"):
                src = self.tasks.resolve_reference(src) or src
            if src:
                self.osc.send("/media", os.path.abspath(str(src)), vol)
        elif otype == "hide_video":
            self.osc.send("/media", os.path.abspath("./assets/image/black.png"), 0.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_speech(self):
        """Start the speech monitor if the show is running and it isn't already streaming."""
        if self.speech and self.state in (ShowState.RUNNING, ShowState.WAITING_FOR_AI):
            if not self.speech.is_streaming():
                self.speech.start()
                logger.info("Speech monitoring started")

    def _register_injected_cues(self, new_steps: list[StepData]):
        """Rebuild the entire cue list after injection so that indices are
        correct and the linear-progression pointer skips already-passed steps."""
        if not self.cue_detector:
            return
        self.cue_detector.clear_all_cues()
        current_idx = self.script.current_index
        for cue in self.script.get_all_cue_phrases():
            self.cue_detector.add_cue(
                phrase=cue["phrase"],
                step_index=cue["step_index"],
                confidence_threshold=cue["confidence"],
            )
            if cue["step_index"] <= current_idx:
                self.cue_detector.mark_step_triggered(cue["step_index"])
        self.cue_detector.reset_transcript()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        text = text.strip()
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"\u201C])', text)
        return [s.strip() for s in sentences if s.strip()]

    # ------------------------------------------------------------------
    # State broadcast
    # ------------------------------------------------------------------

    def _broadcast_state(self):
        if self._on_state_change:
            try:
                self._on_state_change(self.get_state_snapshot())
            except Exception:
                pass

    def get_state_snapshot(self) -> dict:
        current = self.script.current_step
        caption_handler = self.handlers.get("caption")
        return {
            "show_state": self.state.value,
            "show_title": self.script.title,
            "failure_count": self.failure_count,
            "current_step": ScriptManager.step_to_dict(current),
            "current_index": self.script.current_index,
            "total_steps": self.script.total_steps,
            "upcoming_steps": [
                ScriptManager.step_to_dict(s) for s in self.script.get_upcoming(8)
            ],
            "displayed_caption": {
                "text": caption_handler.current_text if caption_handler else "",
                "color": caption_handler.current_color if caption_handler else "#ffffff",
            },
            "loading_message": self._loading_message,
            "transcript": {
                "lines": self.transcript_lines[-12:],
                "partial": self.current_partial,
            },
            "mic": {
                "level": self.speech.get_mic_level() if self.speech and hasattr(self.speech, "get_mic_level") else 0.0,
                "streaming": bool(
                    self.speech and getattr(self.speech, "is_streaming", lambda: False)()
                ),
            },
            "tasks": self.tasks.to_dict(),
            "timer": {
                "remaining": self._timer_remaining,
                "total": self._timer_total,
            },
            "audio_layers": self.audio.get_layer_states() if self.audio else {},
            "steps_outline": self.script.get_steps_outline(),
        }

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self):
        self._next_epoch()
        self.tasks.cancel_all()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._loop_thread.join(timeout=5)
        logger.info("ShowController shut down")

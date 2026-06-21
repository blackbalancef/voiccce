from __future__ import annotations

import subprocess
import time
from datetime import datetime
from pathlib import Path

try:
    import objc
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSBezierPath,
        NSColor,
        NSImageLeft,
        NSImage,
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )
    from Foundation import NSObject, NSTimer
    from PyObjCTools import AppHelper
except Exception as exc:  # pragma: no cover - platform dependent
    objc = None
    NSApplication = None
    NSApplicationActivationPolicyAccessory = None
    NSBezierPath = None
    NSColor = None
    NSImageLeft = None
    NSImage = None
    NSMenu = None
    NSMenuItem = None
    NSStatusBar = None
    NSVariableStatusItemLength = None
    NSObject = object
    NSTimer = None
    AppHelper = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def _python_method(func):
    if objc is None:
        return func
    return objc.python_method(func)

from .config import (
    SUMMARY_MODEL_CHOICES,
    TTS_MODEL_CHOICES,
    VOICE_CHOICES,
    load_config,
    set_events_config,
    set_summary_config,
    set_voice_config,
)
from .runtime import (
    clear_voice_mute,
    clear_voice_pid,
    is_pid_running,
    read_voice_activity_started_at,
    read_voice_pid,
    set_voice_mute,
    stop_speaking,
    voice_mute_status,
)
from .service import daemon_status, service_paths, start_daemon, stop_daemon
from .usage import (
    DashboardData,
    UsageStats,
    format_duration,
    format_usd,
    read_dashboard,
    read_last_voice_channel,
    sparkline,
)


AGENT_LABELS = {"claude-code": "Claude", "codex": "Codex", "pi": "Pi", "other": "Other"}
CHANNEL_LABELS = {"openai_tts": "OpenAI", "macos_say": "say"}


MENU_BAR_ICON_SIZE = 22.0
ROUND_LINE_CAP_STYLE = 1
ROUND_LINE_JOIN_STYLE = 1
ACTIVITY_FRAME_INTERVAL_SECONDS = 0.35
ACTIVITY_WAVE_HEIGHTS = (
    (2.0, 5.0, 3.0),
    (3.5, 2.0, 5.0),
    (5.0, 3.5, 2.0),
    (3.0, 5.0, 3.5),
)
STATIC_WAVE_HEIGHTS = (2.0, 5.0, 2.0)


def format_countdown(seconds: int) -> str:
    seconds = max(0, seconds)
    minutes, second = divmod(seconds, 60)
    hour, minute = divmod(minutes, 60)
    if hour:
        return f"{hour}:{minute:02d}:{second:02d}"
    return f"{minute}:{second:02d}"


def mute_countdown(muted_until: int | None, *, now: float | None = None) -> str | None:
    if muted_until is None:
        return None
    current_time = time.time() if now is None else now
    remaining_seconds = int(max(0, muted_until - current_time))
    return format_countdown(remaining_seconds)


class AgentVoiceMenuBar(NSObject):
    config_path: str | None
    status_item: object
    status_images: dict[bool, object]
    activity_images: dict[bool, list[object]]
    timer: object
    animation_timer: object
    animation_frame_index: int
    active_voice_pid: int | None
    voice_activity_active: bool

    @_python_method
    def setup(self, config_path: str | None) -> None:
        self.config_path = config_path
        self.animation_frame_index = 0
        self.active_voice_pid = None
        self.voice_activity_active = False
        self.status_images = {
            False: self._make_status_image(muted=False),
            True: self._make_status_image(muted=True),
        }
        self.activity_images = {
            False: self._make_activity_images(muted=False),
            True: self._make_activity_images(muted=True),
        }
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            5.0,
            self,
            "refresh:",
            None,
            True,
        )
        self.animation_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            ACTIVITY_FRAME_INTERVAL_SECONDS,
            self,
            "animate:",
            None,
            True,
        )
        self.refresh()

    def refresh_(self, sender) -> None:
        self.refresh()

    def animate_(self, sender) -> None:
        self.animate()

    @_python_method
    def refresh(self) -> None:
        config = load_config(self.config_path)
        mute_status = voice_mute_status(config)
        voice_pid, voice_active = self._voice_activity(config)
        self._update_status_button(
            muted=mute_status.muted,
            mute_remaining=mute_countdown(mute_status.muted_until),
            voice_pid=voice_pid,
            voice_active=voice_active,
        )
        self.status_item.setMenu_(
            self._build_menu(config, voice_pid=voice_pid, voice_active=voice_active)
        )
        self.active_voice_pid = voice_pid
        self.voice_activity_active = voice_active

    @_python_method
    def animate(self) -> None:
        config = load_config(self.config_path)
        mute_status = voice_mute_status(config)
        voice_pid, voice_active = self._voice_activity(config)
        if voice_active:
            self.animation_frame_index = (self.animation_frame_index + 1) % len(ACTIVITY_WAVE_HEIGHTS)
        else:
            self.animation_frame_index = 0
        self._update_status_button(
            muted=mute_status.muted,
            mute_remaining=mute_countdown(mute_status.muted_until),
            voice_pid=voice_pid,
            voice_active=voice_active,
        )
        if voice_pid != self.active_voice_pid or voice_active != self.voice_activity_active:
            self.status_item.setMenu_(
                self._build_menu(config, voice_pid=voice_pid, voice_active=voice_active)
            )
            self.active_voice_pid = voice_pid
            self.voice_activity_active = voice_active

    @_python_method
    def _update_status_button(
        self,
        *,
        muted: bool,
        mute_remaining: str | None,
        voice_pid: int | None,
        voice_active: bool,
    ) -> None:
        button = self.status_item.button()
        if button is None:
            return

        button.setTitle_(mute_remaining or "")
        if voice_active:
            frames = self.activity_images[muted]
            image = frames[self.animation_frame_index % len(frames)]
            tooltip = (
                f"Agent Chime: speaking ({voice_pid})"
                if voice_pid
                else "Agent Chime: preparing voice"
            )
        else:
            image = self.status_images[muted]
            tooltip = f"Agent Chime: muted for {mute_remaining}" if mute_remaining else "Agent Chime"
        button.setImage_(image)
        button.setImagePosition_(NSImageLeft)
        button.setToolTip_(tooltip)

    @_python_method
    def _voice_activity(self, config) -> tuple[int | None, bool]:
        voice_pid = self._active_voice_pid(config)
        return voice_pid, bool(voice_pid or read_voice_activity_started_at(config))

    @_python_method
    def _active_voice_pid(self, config) -> int | None:
        voice_pid = read_voice_pid(config)
        if voice_pid is None:
            return None
        if is_pid_running(voice_pid):
            return voice_pid
        clear_voice_pid(config, voice_pid)
        return None

    @_python_method
    def _make_status_image(self, *, muted: bool, activity_phase: int | None = None) -> object:
        image = NSImage.alloc().initWithSize_((MENU_BAR_ICON_SIZE, MENU_BAR_ICON_SIZE))
        image.lockFocus()
        try:
            NSColor.blackColor().set()
            self._draw_voice_bubble(activity_phase=activity_phase)
            if muted:
                self._draw_mute_slash()
        finally:
            image.unlockFocus()
        image.setTemplate_(True)
        return image

    @_python_method
    def _make_activity_images(self, *, muted: bool) -> list[object]:
        return [
            self._make_status_image(muted=muted, activity_phase=phase)
            for phase in range(len(ACTIVITY_WAVE_HEIGHTS))
        ]

    @_python_method
    def _draw_voice_bubble(self, *, activity_phase: int | None = None) -> None:
        bubble = NSBezierPath.bezierPath()
        bubble.setLineWidth_(1.55)
        bubble.setLineCapStyle_(ROUND_LINE_CAP_STYLE)
        bubble.setLineJoinStyle_(ROUND_LINE_JOIN_STYLE)
        bubble.moveToPoint_((5.6, 5.5))
        bubble.lineToPoint_((7.5, 5.5))
        bubble.lineToPoint_((9.4, 3.6))
        bubble.lineToPoint_((9.8, 5.5))
        bubble.lineToPoint_((16.3, 5.5))
        bubble.curveToPoint_controlPoint1_controlPoint2_((18.5, 7.6), (17.7, 5.5), (18.5, 6.3))
        bubble.lineToPoint_((18.5, 14.1))
        bubble.curveToPoint_controlPoint1_controlPoint2_((16.2, 16.4), (18.5, 15.5), (17.6, 16.4))
        bubble.lineToPoint_((5.8, 16.4))
        bubble.curveToPoint_controlPoint1_controlPoint2_((3.5, 14.1), (4.4, 16.4), (3.5, 15.5))
        bubble.lineToPoint_((3.5, 7.8))
        bubble.curveToPoint_controlPoint1_controlPoint2_((5.6, 5.5), (3.5, 6.4), (4.3, 5.5))
        bubble.stroke()

        heights = STATIC_WAVE_HEIGHTS if activity_phase is None else ACTIVITY_WAVE_HEIGHTS[activity_phase]
        self._draw_waveform(heights)

    @_python_method
    def _draw_waveform(self, heights: tuple[float, float, float]) -> None:
        center_y = 11.0
        x_positions = (7.7, 11.0, 14.3)
        wave = NSBezierPath.bezierPath()
        wave.setLineWidth_(1.75)
        wave.setLineCapStyle_(ROUND_LINE_CAP_STYLE)
        for x_position, height in zip(x_positions, heights, strict=True):
            half_height = height / 2.0
            wave.moveToPoint_((x_position, center_y - half_height))
            wave.lineToPoint_((x_position, center_y + half_height))
        wave.stroke()

    @_python_method
    def _draw_mute_slash(self) -> None:
        slash = NSBezierPath.bezierPath()
        slash.setLineWidth_(2.0)
        slash.setLineCapStyle_(ROUND_LINE_CAP_STYLE)
        slash.moveToPoint_((4.8, 17.0))
        slash.lineToPoint_((17.2, 4.8))
        slash.stroke()

    @_python_method
    def _build_menu(
        self,
        config,
        *,
        voice_pid: int | None = None,
        voice_active: bool | None = None,
    ) -> object:
        menu = NSMenu.alloc().init()
        daemon_pid, daemon_running = daemon_status(config)
        mute_status = voice_mute_status(config)
        if voice_pid is None or voice_active is None:
            voice_pid, voice_active = self._voice_activity(config)

        daemon_label = "Daemon: running" + (f" ({daemon_pid})" if daemon_pid else "") if daemon_running else "Daemon: stopped"
        menu.addItem_(self._item(daemon_label, enabled=False))

        if mute_status.muted and mute_status.muted_until:
            until = datetime.fromtimestamp(mute_status.muted_until).strftime("%H:%M:%S")
            remaining = mute_countdown(mute_status.muted_until)
            voice_label = f"Voice: muted {remaining} left (until {until})"
        else:
            voice_label = "Voice: on"
        if voice_pid:
            voice_label += f" | speaking pid {voice_pid}"
        elif voice_active:
            voice_label += " | preparing audio"
        menu.addItem_(self._item(voice_label, enabled=False))
        self._add_voice_engine_items(menu, config)
        menu.addItem_(NSMenuItem.separatorItem())

        self._add_dashboard_items(menu, config)
        menu.addItem_(NSMenuItem.separatorItem())

        menu.addItem_(self._item("Stop Speaking", "stopSpeaking:"))
        menu.addItem_(self._item("Mute 10 min", "muteTenMinutes:"))
        menu.addItem_(self._item("Mute 1 hour", "muteOneHour:"))
        menu.addItem_(self._item("Unmute", "unmute:"))
        menu.addItem_(NSMenuItem.separatorItem())

        menu.addItem_(self._item("Start Daemon", "startDaemon:", enabled=not daemon_running))
        menu.addItem_(self._item("Stop Daemon", "stopDaemon:", enabled=daemon_running))
        menu.addItem_(NSMenuItem.separatorItem())

        menu.addItem_(self._item("Open Config", "openConfig:"))
        menu.addItem_(self._item("Open Daemon Log", "openDaemonLog:"))
        menu.addItem_(NSMenuItem.separatorItem())

        menu.addItem_(self._item("Quit Menu Bar", "quit:"))
        return menu

    @_python_method
    def _add_voice_engine_items(self, menu: object, config) -> None:
        last_channel = self._read_last_voice_channel(config)
        if last_channel == "openai_tts":
            last_label = "Last spoken: OpenAI TTS"
        elif last_channel == "macos_say":
            if config.voice_backend == "openai_tts":
                last_label = "Last spoken: macOS say ⚠️ (OpenAI fell back)"
            else:
                last_label = "Last spoken: macOS say"
        else:
            last_label = "Last spoken: —"
        menu.addItem_(self._item(last_label, enabled=False))

        self._add_picker_items(menu, config)

    @_python_method
    def _add_picker_items(self, menu: object, config) -> None:
        voice_choices = self._choices_with_current(
            VOICE_CHOICES.get(config.voice_backend, ()), config.voice_name
        )
        menu.addItem_(
            self._submenu_item(
                f"Voice: {config.voice_name or '—'}",
                voice_choices,
                config.voice_name,
                "selectVoice:",
            )
        )

        if config.voice_backend == "openai_tts":
            tts_choices = self._choices_with_current(TTS_MODEL_CHOICES, config.voice_model)
            menu.addItem_(
                self._submenu_item(
                    f"TTS Model: {config.voice_model}",
                    tts_choices,
                    config.voice_model,
                    "selectTtsModel:",
                )
            )

        summary_choices = self._choices_with_current(SUMMARY_MODEL_CHOICES, config.summary_model)
        menu.addItem_(
            self._submenu_item(
                f"Summary Model: {config.summary_model}",
                summary_choices,
                config.summary_model,
                "selectSummaryModel:",
                enabled=config.summary_enabled,
            )
        )

        reminders_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Announce idle reminders", "toggleIdleReminders:", ""
        )
        reminders_item.setTarget_(self)
        reminders_item.setState_(1 if config.notify_input_needed else 0)
        menu.addItem_(reminders_item)

        interrupt_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Stop audio when I reply", "toggleInterruptOnReply:", ""
        )
        interrupt_item.setTarget_(self)
        interrupt_item.setState_(1 if config.voice_interrupt_on_user_input else 0)
        menu.addItem_(interrupt_item)

    @_python_method
    def _choices_with_current(self, choices: tuple[str, ...], current: str | None) -> list[str]:
        result = list(choices)
        if current and current not in result:
            result.insert(0, current)
        return result

    @_python_method
    def _submenu_item(
        self,
        title: str,
        choices: list[str],
        current: str | None,
        action: str,
        *,
        enabled: bool = True,
    ) -> object:
        parent = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, None, "")
        parent.setEnabled_(enabled)
        submenu = NSMenu.alloc().init()
        for choice in choices:
            child = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(choice, action, "")
            child.setTarget_(self)
            child.setRepresentedObject_(choice)
            child.setState_(1 if choice == current else 0)
            child.setEnabled_(enabled)
            submenu.addItem_(child)
        parent.setSubmenu_(submenu)
        return parent

    @_python_method
    def _read_last_voice_channel(self, config) -> str | None:
        try:
            return read_last_voice_channel(config.database_path)
        except Exception as exc:
            self._log(f"Last channel read failed: {exc}")
            return None

    @_python_method
    def _add_dashboard_items(self, menu: object, config) -> None:
        menu.addItem_(self._item("Dashboard (spend)", enabled=False))
        data = self._read_dashboard(config)
        if data is None:
            menu.addItem_(self._item("Stats unavailable", enabled=False))
            return

        menu.addItem_(self._item(self._spend_line("Today", data.today), enabled=False))
        menu.addItem_(self._item(self._spend_line("7 days", data.last_7d), enabled=False))
        menu.addItem_(self._item(self._spend_line("30 days", data.last_30d), enabled=False))
        menu.addItem_(self._item(self._spend_line("All-time", data.all_time), enabled=False))

        spark = sparkline(data.spark_7d)
        if spark:
            menu.addItem_(self._item(f"7-day trend  {spark}", enabled=False))

        agent_line = self._breakdown_line(data.by_agent, AGENT_LABELS)
        if agent_line:
            menu.addItem_(self._item(f"By agent (today): {agent_line}", enabled=False))
        channel_line = self._breakdown_line(data.by_channel, CHANNEL_LABELS)
        if channel_line:
            menu.addItem_(self._item(f"By channel (today): {channel_line}", enabled=False))

    @_python_method
    def _spend_line(self, label: str, stats: UsageStats) -> str:
        total = stats.audio_cost_usd + stats.summary_cost_usd
        return (
            f"{label}: {format_usd(total)} · "
            f"{format_duration(stats.audio_duration_seconds)} · "
            f"{stats.reports_listened_count} spoken"
        )

    @_python_method
    def _breakdown_line(self, rows: list[tuple[str, float, int]], labels: dict[str, str]) -> str:
        parts = [
            f"{labels.get(key, key)} {format_usd(spend)} ({spoken})"
            for key, spend, spoken in rows
            if spoken > 0 or spend > 0
        ]
        return " · ".join(parts)

    @_python_method
    def _read_dashboard(self, config) -> DashboardData | None:
        try:
            return read_dashboard(config.database_path, config.timezone)
        except Exception as exc:
            self._log(f"Dashboard read failed: {exc}")
            return None

    @_python_method
    def _item(self, title: str, action: str | None = None, *, enabled: bool = True) -> object:
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
        item.setEnabled_(enabled)
        if action:
            item.setTarget_(self)
        return item

    @_python_method
    def _config(self):
        return load_config(self.config_path)

    def stopSpeaking_(self, sender) -> None:
        pid = stop_speaking(self._config())
        self._log(f"Stop Speaking clicked; pid={pid or '-'}")
        self.refresh()

    def muteTenMinutes_(self, sender) -> None:
        muted_until = set_voice_mute(self._config(), 10 * 60)
        self._log(f"Mute 10 min clicked; muted_until={muted_until}")
        self.refresh()

    def muteOneHour_(self, sender) -> None:
        muted_until = set_voice_mute(self._config(), 60 * 60)
        self._log(f"Mute 1 hour clicked; muted_until={muted_until}")
        self.refresh()

    def unmute_(self, sender) -> None:
        clear_voice_mute(self._config())
        self._log("Unmute clicked")
        self.refresh()

    def startDaemon_(self, sender) -> None:
        pid = start_daemon(self._config())
        self._log(f"Start Daemon clicked; pid={pid}")
        self.refresh()

    def stopDaemon_(self, sender) -> None:
        pid = stop_daemon(self._config())
        self._log(f"Stop Daemon clicked; pid={pid or '-'}")
        self.refresh()

    def selectVoice_(self, sender) -> None:
        voice = str(sender.representedObject())
        config = self._config()
        set_voice_config(config.config_path, voice=voice)
        self._restart_daemon_if_running()
        self._log(f"Voice set to {voice}")
        self.refresh()

    def selectTtsModel_(self, sender) -> None:
        model = str(sender.representedObject())
        config = self._config()
        set_voice_config(config.config_path, model=model)
        self._restart_daemon_if_running()
        self._log(f"TTS model set to {model}")
        self.refresh()

    def selectSummaryModel_(self, sender) -> None:
        model = str(sender.representedObject())
        config = self._config()
        set_summary_config(config.config_path, model=model)
        self._restart_daemon_if_running()
        self._log(f"Summary model set to {model}")
        self.refresh()

    def toggleIdleReminders_(self, sender) -> None:
        config = self._config()
        new_value = not config.notify_input_needed
        set_events_config(config.config_path, input_needed=new_value)
        self._restart_daemon_if_running()
        self._log(f"Idle reminders {'enabled' if new_value else 'disabled'}")
        self.refresh()

    def toggleInterruptOnReply_(self, sender) -> None:
        config = self._config()
        new_value = not config.voice_interrupt_on_user_input
        set_voice_config(config.config_path, interrupt_on_user_input=new_value)
        # Read fresh by the hook on each invocation — no daemon restart needed.
        self._log(f"Stop-audio-on-reply {'enabled' if new_value else 'disabled'}")
        self.refresh()

    @_python_method
    def _restart_daemon_if_running(self) -> None:
        config = self._config()
        _, running = daemon_status(config)
        if not running:
            return
        stop_daemon(config)
        start_daemon(config)
        self._log("Daemon restarted to apply config change")

    def openConfig_(self, sender) -> None:
        config = self._config()
        subprocess.run(["open", str(config.config_path)], check=False)

    def openDaemonLog_(self, sender) -> None:
        paths = service_paths(self._config())
        paths.log_path.parent.mkdir(parents=True, exist_ok=True)
        paths.log_path.touch(exist_ok=True)
        subprocess.run(["open", str(paths.log_path)], check=False)

    def quit_(self, sender) -> None:
        self._log("Quit Menu Bar clicked")
        NSApplication.sharedApplication().terminate_(self)

    @_python_method
    def _log(self, message: str) -> None:
        print(f"[agent-chime menubar] {datetime.now().isoformat(timespec='seconds')} {message}", flush=True)


def run_menubar(config_path: str | Path | None = None) -> None:
    if _IMPORT_ERROR is not None:
        raise RuntimeError(
            "Menu bar requires pyobjc-framework-Cocoa. Install with "
            "`pip install pyobjc-framework-Cocoa` or `pipx inject agent-chime pyobjc-framework-Cocoa`."
        ) from _IMPORT_ERROR

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    controller = AgentVoiceMenuBar.alloc().init()
    controller.setup(str(config_path) if config_path else None)
    app.setDelegate_(controller)
    AppHelper.runEventLoop()

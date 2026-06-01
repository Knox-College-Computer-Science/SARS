"use client";

import { useState } from "react";
import { usePomodoro } from "./PomodoroProvider";

const MODE_LABELS = {
    focus: "Work",
    short: "Short Break",
    long: "Long Break",
};

export default function PomodoroTimer() {
    const {
        settings,
        mode,
        secondsLeft,
        isRunning,
        completedPomodoros,
        getModeDuration,
        toggleTimer,
        switchMode,
        resetTimer,
        saveTimerSettings,
    } = usePomodoro();

    const [tempSettings, setTempSettings] = useState(settings);
    const [settingsOpen, setSettingsOpen] = useState(false);

    function formatTime(totalSeconds) {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = totalSeconds % 60;

        return `${minutes.toString().padStart(2, "0")}:${seconds
        .toString()
        .padStart(2, "0")}`;
    }

    function updateTempSetting(key, value) {
        setTempSettings((prev) => ({
        ...prev,
        [key]: value,
        }));
    }

    function saveSettings() {
        saveTimerSettings(tempSettings);
        setSettingsOpen(false);
    }

    const totalSeconds = getModeDuration(mode);
    const progress =
        totalSeconds > 0 ? ((totalSeconds - secondsLeft) / totalSeconds) * 100 : 0;

    return (
        <div className="bg-surface-container-low border border-outline-variant rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
            <h3 className="font-display text-base font-semibold flex items-center gap-2">
            <span
                className="material-symbols-outlined text-primary"
                style={{ fontSize: 20 }}
            >
                timer
            </span>
            Pomodoro
            </h3>

            <button
            onClick={() => {
                setTempSettings(settings);
                setSettingsOpen(true);
            }}
            className="text-on-surface-variant hover:text-primary transition-colors"
            aria-label="Pomodoro settings"
            >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>
                settings
            </span>
            </button>
        </div>

        <div className="grid grid-cols-3 gap-2 mb-4">
            {["focus", "short", "long"].map((item) => (
            <button
                key={item}
                onClick={() => switchMode(item, false)}
                className={`px-2 py-1.5 rounded-lg text-xs font-bold transition-all ${
                mode === item
                    ? "bg-primary text-on-primary"
                    : "bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest"
                }`}
            >
                {MODE_LABELS[item]}
            </button>
            ))}
        </div>

        <div className="text-center py-4">
            <p className="text-xs uppercase tracking-widest text-on-surface-variant font-bold mb-2">
            {MODE_LABELS[mode]}
            </p>

            <div className="font-display text-5xl font-bold text-on-surface">
            {formatTime(secondsLeft)}
            </div>

            <p className="text-xs text-on-surface-variant mt-2">
            Completed work sessions: {completedPomodoros}
            </p>
        </div>

        <div className="h-2 w-full bg-surface-container-highest rounded-full overflow-hidden mb-4">
            <div
            className="h-full bg-primary rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
            />
        </div>

        <div className="grid grid-cols-2 gap-2">
            <button
            onClick={toggleTimer}
            className="py-2 rounded-lg bg-primary text-on-primary text-sm font-bold hover:brightness-110 transition"
            >
            {isRunning ? "Pause" : "Start"}
            </button>

            <button
            onClick={resetTimer}
            className="py-2 rounded-lg bg-surface-container-high text-on-surface text-sm font-bold hover:bg-surface-container-highest transition"
            >
            Reset
            </button>
        </div>

        {settingsOpen && (
            <div className="fixed inset-0 z-[9999] bg-black/60 flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-surface-container border border-outline-variant rounded-xl p-6 shadow-2xl">
                <div className="flex items-center justify-between mb-5">
                <h2 className="font-display text-xl font-bold text-on-surface">
                    Timer Settings
                </h2>

                <button
                    onClick={() => setSettingsOpen(false)}
                    className="text-on-surface-variant hover:text-error transition"
                >
                    <span className="material-symbols-outlined">close</span>
                </button>
                </div>

                <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-3">
                Time minutes
                </p>

                <div className="grid grid-cols-3 gap-3 mb-5">
                <label className="text-xs font-bold text-on-surface-variant">
                    Pomodoro
                    <input
                    type="number"
                    min="1"
                    value={tempSettings.focusMinutes}
                    onChange={(e) =>
                        updateTempSetting("focusMinutes", e.target.value)
                    }
                    className="mt-1 w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:border-primary"
                    />
                </label>

                <label className="text-xs font-bold text-on-surface-variant">
                    Short Break
                    <input
                    type="number"
                    min="1"
                    value={tempSettings.shortBreakMinutes}
                    onChange={(e) =>
                        updateTempSetting("shortBreakMinutes", e.target.value)
                    }
                    className="mt-1 w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:border-primary"
                    />
                </label>

                <label className="text-xs font-bold text-on-surface-variant">
                    Long Break
                    <input
                    type="number"
                    min="1"
                    value={tempSettings.longBreakMinutes}
                    onChange={(e) =>
                        updateTempSetting("longBreakMinutes", e.target.value)
                    }
                    className="mt-1 w-full bg-surface-container-lowest border border-outline-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:border-primary"
                    />
                </label>
                </div>

                <div className="space-y-4 mb-5">
                <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface">
                    Auto Start Breaks
                    </span>

                    <button
                    onClick={() =>
                        updateTempSetting(
                        "autoStartBreaks",
                        !tempSettings.autoStartBreaks
                        )
                    }
                    className={`w-12 h-7 rounded-full p-1 transition ${
                        tempSettings.autoStartBreaks
                        ? "bg-primary"
                        : "bg-surface-container-highest"
                    }`}
                    >
                    <div
                        className={`w-5 h-5 bg-white rounded-full transition-transform ${
                        tempSettings.autoStartBreaks ? "translate-x-5" : ""
                        }`}
                    />
                    </button>
                </div>

                <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface">
                    Auto Start Pomodoros
                    </span>

                    <button
                    onClick={() =>
                        updateTempSetting(
                        "autoStartPomodoros",
                        !tempSettings.autoStartPomodoros
                        )
                    }
                    className={`w-12 h-7 rounded-full p-1 transition ${
                        tempSettings.autoStartPomodoros
                        ? "bg-primary"
                        : "bg-surface-container-highest"
                    }`}
                    >
                    <div
                        className={`w-5 h-5 bg-white rounded-full transition-transform ${
                        tempSettings.autoStartPomodoros ? "translate-x-5" : ""
                        }`}
                    />
                    </button>
                </div>

                <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-on-surface">
                    Long Break Interval
                    </span>

                    <input
                    type="number"
                    min="1"
                    value={tempSettings.longBreakInterval}
                    onChange={(e) =>
                        updateTempSetting("longBreakInterval", e.target.value)
                    }
                    className="w-20 bg-surface-container-lowest border border-outline-variant rounded-lg px-3 py-2 text-on-surface outline-none focus:border-primary"
                    />
                </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                <button
                    onClick={() => setSettingsOpen(false)}
                    className="py-2 rounded-lg bg-surface-container-high text-on-surface text-sm font-bold hover:bg-surface-container-highest transition"
                >
                    Cancel
                </button>

                <button
                    onClick={saveSettings}
                    className="py-2 rounded-lg bg-primary text-on-primary text-sm font-bold hover:brightness-110 transition"
                >
                    Save Settings
                </button>
                </div>
            </div>
            </div>
        )}
        </div>
    );
}
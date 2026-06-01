"use client";

import {
    createContext,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";

const DEFAULT_SETTINGS = {
    focusMinutes: 25,
    shortBreakMinutes: 5,
    longBreakMinutes: 15,
    longBreakInterval: 4,
    autoStartBreaks: false,
    autoStartPomodoros: false,
};

const STORAGE_SETTINGS_KEY = "sars-pomodoro-settings";
const STORAGE_STATE_KEY = "sars-pomodoro-state";

const PomodoroContext = createContext(null);

function getDurationForMode(mode, settings) {
    if (mode === "focus") return settings.focusMinutes * 60;
    if (mode === "short") return settings.shortBreakMinutes * 60;
    return settings.longBreakMinutes * 60;
}

export function PomodoroProvider({ children }) {
    const [settings, setSettings] = useState(DEFAULT_SETTINGS);
    const [mode, setMode] = useState("focus");
    const [secondsLeft, setSecondsLeft] = useState(
        DEFAULT_SETTINGS.focusMinutes * 60
    );
    const [isRunning, setIsRunning] = useState(false);
    const [completedPomodoros, setCompletedPomodoros] = useState(0);
    const [endTime, setEndTime] = useState(null);

    const audioContextRef = useRef(null);
    const completionLockRef = useRef(false);

    useEffect(() => {
        const savedSettings = localStorage.getItem(STORAGE_SETTINGS_KEY);

        let loadedSettings = DEFAULT_SETTINGS;

        if (savedSettings) {
        try {
            loadedSettings = {
            ...DEFAULT_SETTINGS,
            ...JSON.parse(savedSettings),
            };
        } catch {
            localStorage.removeItem(STORAGE_SETTINGS_KEY);
        }
        }

        setSettings(loadedSettings);

        const savedState = localStorage.getItem(STORAGE_STATE_KEY);

        if (savedState) {
        try {
            const parsedState = JSON.parse(savedState);

            const savedMode = parsedState.mode || "focus";
            const savedCompleted = parsedState.completedPomodoros || 0;

            setMode(savedMode);
            setCompletedPomodoros(savedCompleted);

            if (parsedState.isRunning && parsedState.endTime) {
            const remaining = Math.ceil(
                (parsedState.endTime - Date.now()) / 1000
            );

            if (remaining > 0) {
                setSecondsLeft(remaining);
                setEndTime(parsedState.endTime);
                setIsRunning(true);
            } else {
                setSecondsLeft(getDurationForMode(savedMode, loadedSettings));
                setEndTime(null);
                setIsRunning(false);
            }
            } else {
            setSecondsLeft(
                parsedState.secondsLeft ||
                getDurationForMode(savedMode, loadedSettings)
            );
            setEndTime(null);
            setIsRunning(false);
            }
        } catch {
            localStorage.removeItem(STORAGE_STATE_KEY);
            setSecondsLeft(loadedSettings.focusMinutes * 60);
        }
        } else {
        setSecondsLeft(loadedSettings.focusMinutes * 60);
        }
    }, []);

    useEffect(() => {
        localStorage.setItem(
        STORAGE_STATE_KEY,
        JSON.stringify({
            mode,
            secondsLeft,
            isRunning,
            completedPomodoros,
            endTime,
        })
        );
    }, [mode, secondsLeft, isRunning, completedPomodoros, endTime]);

    useEffect(() => {
        if (!isRunning || !endTime) return;

        const interval = setInterval(() => {
        const remaining = Math.ceil((endTime - Date.now()) / 1000);

        if (remaining > 0) {
            setSecondsLeft(remaining);
        } else {
            setSecondsLeft(0);
            handleTimerComplete();
        }
        }, 500);

        return () => clearInterval(interval);
    }, [isRunning, endTime, mode, settings, completedPomodoros]);

    function getAudioContext() {
        if (typeof window === "undefined") return null;

        const AudioContext = window.AudioContext || window.webkitAudioContext;

        if (!AudioContext) return null;

        if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext();
        }

        if (audioContextRef.current.state === "suspended") {
        audioContextRef.current.resume();
        }

        return audioContextRef.current;
    }

    function primeAudio() {
        getAudioContext();
    }

    function playTimerEndSound() {
        try {
        const audioContext = getAudioContext();

        if (!audioContext) return;

        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(880, audioContext.currentTime);

        gainNode.gain.setValueAtTime(0.25, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(
            0.001,
            audioContext.currentTime + 0.9
        );

        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);

        oscillator.start();
        oscillator.stop(audioContext.currentTime + 0.9);
        } catch (err) {
        console.error("Failed to play timer sound:", err);
        }
    }

    function handleTimerComplete() {
        if (completionLockRef.current) return;

        completionLockRef.current = true;

        playTimerEndSound();

        if (mode === "focus") {
        const nextCompleted = completedPomodoros + 1;
        const shouldLongBreak =
            nextCompleted % settings.longBreakInterval === 0;
        const nextMode = shouldLongBreak ? "long" : "short";
        const nextDuration = getDurationForMode(nextMode, settings);

        setCompletedPomodoros(nextCompleted);
        setMode(nextMode);
        setSecondsLeft(nextDuration);

        if (settings.autoStartBreaks) {
            setEndTime(Date.now() + nextDuration * 1000);
            setIsRunning(true);
        } else {
            setEndTime(null);
            setIsRunning(false);
        }
        } else {
        const nextDuration = getDurationForMode("focus", settings);

        setMode("focus");
        setSecondsLeft(nextDuration);

        if (settings.autoStartPomodoros) {
            setEndTime(Date.now() + nextDuration * 1000);
            setIsRunning(true);
        } else {
            setEndTime(null);
            setIsRunning(false);
        }
        }

        setTimeout(() => {
        completionLockRef.current = false;
        }, 800);
    }

    function toggleTimer() {
        if (isRunning) {
        const remaining = endTime
            ? Math.max(0, Math.ceil((endTime - Date.now()) / 1000))
            : secondsLeft;

        setSecondsLeft(remaining);
        setEndTime(null);
        setIsRunning(false);
        return;
        }

        primeAudio();

        setEndTime(Date.now() + secondsLeft * 1000);
        setIsRunning(true);
    }

    function switchMode(newMode, shouldRun = false) {
        const duration = getDurationForMode(newMode, settings);

        setMode(newMode);
        setSecondsLeft(duration);

        if (shouldRun) {
        primeAudio();
        setEndTime(Date.now() + duration * 1000);
        setIsRunning(true);
        } else {
        setEndTime(null);
        setIsRunning(false);
        }
    }

    function resetTimer() {
        const duration = getDurationForMode(mode, settings);

        setIsRunning(false);
        setEndTime(null);
        setSecondsLeft(duration);
    }

    function saveTimerSettings(newSettings) {
        const cleaned = {
        focusMinutes: Math.max(1, Number(newSettings.focusMinutes) || 25),
        shortBreakMinutes: Math.max(
            1,
            Number(newSettings.shortBreakMinutes) || 5
        ),
        longBreakMinutes: Math.max(
            1,
            Number(newSettings.longBreakMinutes) || 15
        ),
        longBreakInterval: Math.max(
            1,
            Number(newSettings.longBreakInterval) || 4
        ),
        autoStartBreaks: Boolean(newSettings.autoStartBreaks),
        autoStartPomodoros: Boolean(newSettings.autoStartPomodoros),
        };

        setSettings(cleaned);
        localStorage.setItem(STORAGE_SETTINGS_KEY, JSON.stringify(cleaned));

        setIsRunning(false);
        setEndTime(null);
        setSecondsLeft(getDurationForMode(mode, cleaned));
    }

    function getModeDuration(selectedMode) {
        return getDurationForMode(selectedMode, settings);
    }

    const value = {
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
    };

    return (
        <PomodoroContext.Provider value={value}>
        {children}
        </PomodoroContext.Provider>
    );
}

export function usePomodoro() {
    const context = useContext(PomodoroContext);

    if (!context) {
        throw new Error("usePomodoro must be used inside PomodoroProvider");
    }

    return context;
}
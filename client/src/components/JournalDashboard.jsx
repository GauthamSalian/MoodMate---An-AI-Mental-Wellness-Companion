import React, { useState, useEffect } from "react";
import Calendar from "react-calendar";
import "react-calendar/dist/Calendar.css";
import { parseISO } from "date-fns";
import { Zap, TrendingUp, ShieldCheck, Heart, Sparkles, CalendarCheck } from 'lucide-react';

const BASE_URL = "http://localhost:8001";

const agenticColors = {
    strength: "#FFC72C",
    action: "#4EE581",
    reflection: "#B8B0FF",
    essence: "#00CCFF",
};

const riskColors = {
    HIGH: "#FF4D4F",
    MEDIUM: "#FFA940",
    LOW: "#52C41A"
};

const MAX_LENGTH = 1000;

const JournalDashboard = () => {
    const [entry, setEntry] = useState("");
    const [charCount, setCharCount] = useState(0);
    const [savedEntry, setSavedEntry] = useState(null);
    const [entries, setEntries] = useState([]);
    const [selectedDate, setSelectedDate] = useState(new Date());
    const [isEditing, setIsEditing] = useState(false);
    const [isViewing, setIsViewing] = useState(false);
    const [showSuggestion, setShowSuggestion] = useState(false);
    const [safeMode, setSafeMode] = useState(false);

    const prompt = "How was your day? What emotions stood out?";

    useEffect(() => {
        // Fetch all analysis items
        fetch(`${BASE_URL}/journal-entries`)
            .then((res) => res.json())
            .then((data) => {
                if (Array.isArray(data)) {
                    // The backend's schema currently does NOT return date/id/text.
                    // Keep them as returned; front-end will handle absent date gracefully.
                    setEntries(data);
                } else {
                    console.error("Expected array but got:", data);
                    setEntries([]);
                }
            })
            .catch((err) => {
                console.error("Error fetching entries:", err);
                setEntries([]);
            });
    }, [savedEntry]);

    const handleSave = async () => {
        const formattedDate = selectedDate.toISOString().split("T")[0];
        const url = `${BASE_URL}/journal-entry`;

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    text: entry.replace(/[^\x20-\x7E]/g, ""),
                }),
            });

            if (!response.ok) {
                const errBody = await response.text();
                throw new Error(errBody || "Failed to save");
            }

            const data = await response.json();
            // Save local text with analysis for the UI, because the backend does not return text.
            setSavedEntry({ text: entry, ...data, date: formattedDate });
            setEntry("");
            setCharCount(0);
            setIsEditing(false);

            // Optionally update the calendar listing — the returned objects may not include dates,
            // but we'll add this local item to entries array so the UI can show a dot.
            const localItem = { ...data, text: entry, date: formattedDate };
            setEntries((prev) => [localItem, ...prev]);
        } catch (err) {
            console.error("Error creating journal entry:", err);
        }
    };

    const handleDelete = () => {
        setEntry("");
        setSavedEntry(null);
        // The backend currently has no delete endpoint in newjournal.py
    };

    // A helper to get risk color for a date if we have entries with 'date'
    const getRiskForDate = (date) => {
        const formatted = date.toISOString().split("T")[0];
        const match = entries.find((e) => e.date === formatted);
        if (!match) return null;
        return match.overall_risk_level || null;
    };

    const tileContent = ({ date }) => {
        const level = getRiskForDate(date);
        if (!level) return null;
        return (
            <div className="w-2 h-2 rounded-full mx-auto mt-1"
                style={{ backgroundColor: riskColors[level] || "#ccc" }} />
        );
    };

    const fetchEntryByDate = async (date) => {
        const formattedDate = date.toISOString().split("T")[0];
        console.log("Fetching for date:", formattedDate);
        setSelectedDate(date);

        try {
            // newjournal.py expects ?date=YYYY-MM-DD as the query name
            const res = await fetch(`${BASE_URL}/journal-entry/by-date?date=${formattedDate}`);

            if (!res.ok) {
                // No entry found; clear local state
                setSavedEntry(null);
                setIsEditing(false);
                setIsViewing(true);
                setEntry("");
                return;
            }

            const data = await res.json();
            // The backend response doesn't contain the original text in the current newjournal.py,
            // so we set savedEntry with available analysis fields. The text won't be editable (no ID).
            setSavedEntry({ text: data.text || "", ...data, date: formattedDate });
            setIsEditing(false);
            setIsViewing(true);

            // If text is returned (in a future update), populate the editor
            setEntry(data.text || "");
            setCharCount((data.text || "").length);
        } catch (err) {
            console.error("Error fetching entry:", err);
        }
    };

    const renderList = (items, color) => (
        <ul className="list-disc list-inside space-y-2">
            {items.map((item, index) => (
                <li key={index} className="flex items-start text-gray-700 dark:text-gray-300">
                    <Zap size={16} className={`mr-2 flex-shrink-0`} style={{ color }} />
                    <span className="text-sm">{item}</span>
                </li>
            ))}
        </ul>
    );

    return (
        <div className="w-full h-screen p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow p-4 h-full md:col-span-2">
                <h2 className="text-xl font-semibold text-gray-800 dark:text-white mb-2">
                    Daily Journal
                </h2>

                {!savedEntry || isEditing ? (
                    <>
                        <p className="text-sm text-gray-500 italic mb-2">{prompt}</p>
                        <textarea
                            className="w-full h-80 p-3 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-900 dark:text-white resize-none"
                            value={entry}
                            onChange={(e) => {
                                setEntry(e.target.value);
                                setCharCount(e.target.value.length);
                            }}
                            maxLength={MAX_LENGTH}
                            placeholder="Write your thoughts here..."
                        />
                        <div className="flex justify-between items-center mt-2">
                            <span className="text-sm text-gray-500 dark:text-gray-400">
                                {charCount}/{MAX_LENGTH}
                            </span>
                            <button
                                onClick={handleSave}
                                className="px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700"
                                disabled={entry.trim() === ""}
                            >
                                Save
                            </button>
                            <button
                                onClick={() => {
                                    setIsEditing(false);
                                    setIsViewing(true);
                                    if (savedEntry && savedEntry.entry_text) {
                                        setEntry(savedEntry.entry_text);
                                        setCharCount(savedEntry.entry_text.length);
                                    } else {
                                        setEntry("");
                                        setCharCount(0);
                                    }
                                }}
                                className="px-4 py-2 bg-gray-500 text-white rounded-xl hover:bg-gray-600 ml-2"
                            >
                                Cancel
                            </button>
                        </div>
                    </>
                ) : (
                    <>
                        <div className="bg-gray-100 dark:bg-gray-900 p-3 rounded-lg text-gray-800 dark:text-gray-100 min-h-60 mb-4">
                            {/* If the backend doesn't return the journal text, we still show the original local text if present */}
                            <p>{savedEntry.entry_text || "Journal text not available from backend."}</p>

                            {isViewing && (
                                <div className="flex gap-2 mt-4">
                                    {/* Editing is disabled for server-backed entries until backend supports returning ID/text */}
                                    <button
                                        onClick={() => {
                                            setIsEditing(true);
                                            setIsViewing(false);
                                            // If backend returns editable text later, we'll populate editor.
                                            if (savedEntry.entry_text) {
                                                setEntry(savedEntry.entry_text);
                                                setCharCount(savedEntry.entry_text.length);
                                            }
                                        }}
                                        className={`px-4 py-2 ${savedEntry.text ? "bg-yellow-500" : "bg-gray-400"} text-white rounded-xl ml-0`}
                                        disabled={!savedEntry.entry_text}
                                    >
                                        ✏️ Edit
                                    </button>
                                    <button
                                        onClick={handleDelete}
                                        className="px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600"
                                    >
                                        🗑️ Delete
                                    </button>
                                </div>
                            )}
                        </div>

                        {/* NEW AGENTIC ANALYSIS BLOCKS */}
                        {!safeMode && savedEntry && (
                            <div className="space-y-4">
                                {/* Core Theme */}
                                <div className="p-3 bg-blue-50 dark:bg-blue-900 rounded-lg shadow-inner">
                                    <h3 className="flex items-center font-bold text-lg mb-1" style={{ color: agenticColors.essence }}>
                                        <Heart size={20} className="mr-2" /> The Core Theme
                                    </h3>
                                    <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                                        {savedEntry.essence_theme || "No theme available."}
                                    </p>
                                </div>

                                {/* Identified Strengths */}
                                <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded-lg shadow-inner">
                                    <h3 className="flex items-center font-bold text-lg mb-3" style={{ color: agenticColors.strength }}>
                                        <TrendingUp size={20} className="mr-2" /> Your Inner Strengths
                                    </h3>
                                    {renderList(savedEntry.identified_strengths || [], agenticColors.strength)}
                                </div>

                                {/* Historical Pattern */}
                                <div className="p-3 bg-purple-50 dark:bg-purple-900 rounded-lg shadow-inner">
                                    <h3 className="flex items-center font-bold text-lg mb-3 text-purple-600 dark:text-purple-400">
                                        <Sparkles size={20} className="mr-2" /> Historical Pattern
                                    </h3>
                                    <p className="text-sm text-gray-700 dark:text-gray-300 italic">
                                        {savedEntry.historical_pattern || "No clear recurring pattern detected yet."}
                                    </p>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>

            <div className="flex flex-col space-y-4">
                <div className="bg-white dark:bg-gray-800 p-4 rounded-xl shadow">
                    <h2 className="text-lg font-semibold text-gray-800 dark:text-white mb-2">
                        Emotion Calendar
                    </h2>
                    <Calendar
                        tileContent={tileContent}
                        onClickDay={fetchEntryByDate}
                    />
                </div>

                <div className="mb-4 flex items-center space-x-2">
                    <input
                        type="checkbox"
                        checked={safeMode}
                        onChange={() => setSafeMode(!safeMode)}
                        id="safe-mode"
                        className="accent-blue-600"
                    />
                    <label htmlFor="safe-mode" className="text-sm text-gray-700 dark:text-gray-300">
                        Enable Safe Mode (hide analysis)
                    </label>
                </div>

                {!safeMode && savedEntry && (
                    <>
                        <div className="bg-yellow-50 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200 p-4 rounded-xl shadow">
                            <h2 className="text-lg font-semibold mb-2 flex items-center">
                                <ShieldCheck size={20} className="mr-2" /> Reframing & Insight
                            </h2>
                            <p className="text-sm">{savedEntry.reappraisal_message || "No reframing message available."}</p>
                        </div>

                        <div className="bg-green-50 dark:bg-green-900 text-green-800 dark:text-green-200 p-4 rounded-xl shadow">
                            <h2 className="text-lg font-semibold mb-2 flex items-center">
                                <CalendarCheck size={20} className="mr-2" /> Actionable Cues (Proactive)
                            </h2>
                            <p className="text-sm italic mb-3">
                                Ready to be scheduled for Morning, Mid-day, and Evening reinforcement:
                            </p>
                            {renderList(savedEntry.coping_suggestions || [], agenticColors.action)}

                            <button
                                onClick={() => alert("Simulating Habit Flow update and Notification Scheduling...")}
                                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 text-sm w-full"
                            >
                                🎯 Schedule 3 New Cues Now
                            </button>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
};

export default JournalDashboard;
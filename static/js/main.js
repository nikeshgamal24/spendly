// main.js — profile date filter preset logic

(function () {
    function toISO(date) {
        return date.toISOString().slice(0, 10);
    }

    function computePresetRange(preset) {
        const today = new Date();
        const todayStr = toISO(today);

        if (preset === "all-time") return null;

        if (preset === "this-month") {
            const start = new Date(today.getFullYear(), today.getMonth(), 1);
            return { from: toISO(start), to: todayStr };
        }

        if (preset === "last-3-months") {
            const start = new Date(today);
            start.setMonth(start.getMonth() - 3);
            return { from: toISO(start), to: todayStr };
        }

        if (preset === "last-6-months") {
            const start = new Date(today);
            start.setMonth(start.getMonth() - 6);
            return { from: toISO(start), to: todayStr };
        }

        return null;
    }

    function getActivePreset(currentFrom, currentTo) {
        if (!currentFrom && !currentTo) return "all-time";

        const presets = ["this-month", "last-3-months", "last-6-months"];
        for (const preset of presets) {
            const range = computePresetRange(preset);
            if (range && range.from === currentFrom && range.to === currentTo) {
                return preset;
            }
        }
        return null;
    }

    function initFilterPresets() {
        const presetBtns = document.querySelectorAll(".profile-filter-preset");
        if (!presetBtns.length) return;

        const fromInput = document.getElementById("filter-from");
        const toInput   = document.getElementById("filter-to");
        const form      = document.getElementById("profile-filter-form");
        if (!fromInput || !toInput || !form) return;

        // Mark the currently active preset.
        const active = getActivePreset(fromInput.value, toInput.value);
        presetBtns.forEach(btn => {
            if (btn.dataset.preset === active) {
                btn.classList.add("profile-filter-preset--active");
            }
        });

        presetBtns.forEach(btn => {
            btn.addEventListener("click", function () {
                const preset = this.dataset.preset;

                if (preset === "all-time") {
                    window.location.href = form.action;
                    return;
                }

                const range = computePresetRange(preset);
                if (!range) return;

                fromInput.value = range.from;
                toInput.value   = range.to;
                form.submit();
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initFilterPresets);
    } else {
        initFilterPresets();
    }
}());

"use client";
import { useEffect, useState } from "react";
import { Icon } from "./Icon";

type Theme = "dark" | "light";
const KEY = "studio-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);
  useEffect(() => setTheme(document.documentElement.classList.contains("light") ? "light" : "dark"), []);
  const flip = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.classList.toggle("light", next === "light");
    try { localStorage.setItem(KEY, next); } catch {}
    setTheme(next);
  };
  return (
    <button onClick={flip} aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"} title={theme === "light" ? "Dark theme" : "Light theme"}
      className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-surface text-slate-400 transition hover:border-slate-500 hover:text-slate-100">
      <Icon name={theme === "light" ? "moon" : "sun"} className="h-4 w-4" />
    </button>
  );
}

/** Runs before hydration so the saved/system theme is applied without a flash. */
export const THEME_INIT = `try{var t=localStorage.getItem("${KEY}");if(!t)t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";if(t==="light")document.documentElement.classList.add("light")}catch(e){}`;

import { useRef, useCallback, type KeyboardEvent, type ReactNode } from "react";

export interface TabDef {
  id: string;
  label: string;
  badge?: string;
}

interface TabsProps {
  tabs: TabDef[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export function TabList({ tabs, activeTab, onTabChange }: TabsProps) {
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent, index: number) => {
      let next = index;
      if (e.key === "ArrowRight") next = (index + 1) % tabs.length;
      else if (e.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
      else if (e.key === "Home") next = 0;
      else if (e.key === "End") next = tabs.length - 1;
      else return;
      e.preventDefault();
      tabRefs.current[next]?.focus();
      onTabChange(tabs[next].id);
    },
    [tabs, onTabChange],
  );

  return (
    <div
      role="tablist"
      className="flex gap-6 overflow-x-auto border-b border-[#21262d] pb-0"
    >
      {tabs.map((tab, i) => {
        const active = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            ref={(el) => { tabRefs.current[i] = el; }}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={active}
            aria-controls={`panel-${tab.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onTabChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            className={`shrink-0 whitespace-nowrap pb-3 text-sm font-medium transition-colors duration-150 ${
              active
                ? "border-b-2 border-amber-500 text-ink-100"
                : "text-ink-500 hover:text-ink-300"
            }`}
          >
            {tab.label}
            {tab.badge != null && ` (${tab.badge})`}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  id: string;
  activeTab: string;
  children: ReactNode;
}

export function TabPanel({ id, activeTab, children }: TabPanelProps) {
  if (id !== activeTab) return null;
  return (
    <div
      role="tabpanel"
      id={`panel-${id}`}
      aria-labelledby={`tab-${id}`}
      className="pt-6"
    >
      {children}
    </div>
  );
}

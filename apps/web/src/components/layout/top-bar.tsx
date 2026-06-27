"use client";

import { Bell, ChevronDown, HelpCircle, History, LogOut } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function TopBar() {
  const { user, logout } = useAuth();

  return (
    <header
      className="fixed top-0 left-[260px] right-0 h-16 flex items-center justify-between px-8 z-10 border-b"
      style={{
        background: "var(--surface-container-lowest)",
        borderColor: "var(--outline-variant)",
        boxShadow: "0px 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      {/* Left: top-level nav tabs */}
      <nav className="hidden lg:flex items-center gap-6">
        <button
          className="text-[13px] font-bold pb-1 border-b-2 transition-all"
          style={{
            color: "var(--primary)",
            borderColor: "var(--primary)",
          }}
        >
          Analytics
        </button>
        <button
          className="text-[13px] pb-1 border-b-2 border-transparent transition-all hover:border-[var(--primary)]"
          style={{ color: "var(--on-surface-variant)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--primary)")}
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--on-surface-variant)")
          }
        >
          Reports
        </button>
        <button
          className="text-[13px] pb-1 border-b-2 border-transparent transition-all"
          style={{ color: "var(--on-surface-variant)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--primary)")}
          onMouseLeave={(e) =>
            (e.currentTarget.style.color = "var(--on-surface-variant)")
          }
        >
          Audit Log
        </button>
      </nav>

      {/* Right: actions + profile */}
      <div className="flex items-center gap-3 ml-auto">
        {/* Icon buttons */}
        <div className="flex items-center gap-1">
          <button
            className="p-2 rounded-full transition-colors"
            style={{ color: "var(--on-surface-variant)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--surface-container-high)";
              e.currentTarget.style.color = "var(--primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--on-surface-variant)";
            }}
            title="History"
          >
            <History className="w-4 h-4" />
          </button>
          <button
            className="p-2 rounded-full transition-colors"
            style={{ color: "var(--on-surface-variant)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--surface-container-high)";
              e.currentTarget.style.color = "var(--primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--on-surface-variant)";
            }}
            title="Help"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
          <button
            className="relative p-2 rounded-full transition-colors"
            style={{ color: "var(--on-surface-variant)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--surface-container-high)";
              e.currentTarget.style.color = "var(--primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "var(--on-surface-variant)";
            }}
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
          </button>
        </div>

        {/* Divider */}
        <div
          className="w-px h-6"
          style={{ background: "var(--outline-variant)" }}
        />

        {/* User dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--surface-container-low)] active:scale-95">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold text-white shrink-0"
              style={{ background: "var(--primary)" }}
            >
              {user?.name?.slice(0, 2).toUpperCase() ?? "LG"}
            </div>
            {user && (
              <span
                className="hidden sm:block text-[13px] font-medium max-w-[140px] truncate"
                style={{ color: "var(--on-surface)" }}
              >
                {user.name}
              </span>
            )}
            <ChevronDown
              className="w-3.5 h-3.5 shrink-0"
              style={{ color: "var(--on-surface-variant)" }}
            />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            {user && (
              <>
                <div className="px-3 py-2">
                  <p
                    className="text-[13px] font-semibold truncate"
                    style={{ color: "var(--on-surface)" }}
                  >
                    {user.name}
                  </p>
                  <p
                    className="text-[11px] truncate"
                    style={{ color: "var(--on-surface-variant)" }}
                  >
                    {user.email}
                  </p>
                </div>
                <DropdownMenuSeparator />
              </>
            )}
            <DropdownMenuItem
              onClick={logout}
              className="gap-2 text-[13px] cursor-pointer"
              style={{ color: "var(--error)" }}
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}

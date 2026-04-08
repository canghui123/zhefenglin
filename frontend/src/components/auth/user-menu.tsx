"use client";

import { useSession } from "./session-provider";

export function UserMenu() {
  const { user, logout, loading } = useSession();

  if (loading) {
    return (
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        加载中...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        v0.1.0 MVP
      </div>
    );
  }

  return (
    <div className="p-4 border-t border-slate-700 text-xs text-slate-400 space-y-2">
      <div>
        <div className="text-slate-200 font-medium truncate">
          {user.display_name || user.email}
        </div>
        <div className="uppercase tracking-wider text-[10px] text-slate-500">
          {user.role}
        </div>
      </div>
      <button
        type="button"
        onClick={logout}
        className="w-full text-left text-slate-300 hover:text-white"
      >
        退出登录
      </button>
    </div>
  );
}

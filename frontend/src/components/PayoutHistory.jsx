import { useState } from "react";
import { formatINR } from "../api/client";

const STATUS = {
  pending:    { label: "Pending",    cls: "bg-amber-50 text-amber-600 border-amber-100",   dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse" },
  processing: { label: "Processing", cls: "bg-blue-50 text-blue-600 border-blue-100",     dot: "bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.6)] animate-pulse" },
  completed:  { label: "Completed",  cls: "bg-emerald-50 text-emerald-600 border-emerald-100", dot: "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" },
  failed:     { label: "Failed",     cls: "bg-red-50 text-red-600 border-red-100",         dot: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]" },
};

const TABS = ["all", "pending", "processing", "completed", "failed"];

function Badge({ status }) {
  const s = STATUS[status] || STATUS.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold px-2.5 py-1 rounded-lg border uppercase tracking-wider ${s.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

export default function PayoutHistory({ payouts, loading }) {
  const [tab, setTab] = useState("all");
  const list = tab === "all" ? payouts : payouts.filter((p) => p.status === tab);
  const count = (s) => payouts.filter((p) => p.status === s).length;

  return (
    <div className="premium-card !p-0 overflow-hidden animate-slide-up">
      {/* Header & Filter */}
      <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900 tracking-tight">Payout History</h2>
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">{payouts.length} Recorded Withdrawals</p>
          </div>
          
          <div className="flex bg-slate-100/50 p-1 rounded-xl">
            {TABS.map((t) => {
              const n = t === "all" ? payouts.length : count(t);
              const isSelected = tab === t;
              return (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all duration-200
                    ${isSelected 
                      ? "bg-white text-slate-900 shadow-sm" 
                      : "text-slate-400 hover:text-slate-600"}`}
                >
                  {t}
                  {n > 0 && <span className={`ml-1.5 opacity-50 ${isSelected ? "text-brand-500" : ""}`}>{n}</span>}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Table Content */}
      {loading && payouts.length === 0 ? (
        <div className="p-8 space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 bg-slate-50 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : list.length === 0 ? (
        <div className="py-20 text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-300 mb-4">
            <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em]">No {tab !== "all" ? tab : ""} payouts found</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50/30">
                {["Amount", "Status", "Bank Info", "Processed On", "Attempts"].map((h) => (
                  <th key={h} className="px-8 py-4 text-left text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.map((p, i) => (
                <tr
                  key={p.id}
                  className="group hover:bg-slate-50/50 transition-all duration-200 animate-fade-in"
                  style={{ animationDelay: `${i * 20}ms` }}
                >
                  <td className="px-6 py-4">
                    <span className="text-sm font-bold text-slate-900 tabular-nums tracking-tight">{formatINR(p.amount_paise)}</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1.5">
                      <Badge status={p.status} />
                      {p.status === "failed" && p.failure_reason && (
                        <span className="text-[9px] font-medium text-red-400 truncate max-w-[120px]" title={p.failure_reason}>
                          {p.failure_reason}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2 text-slate-400">
                      <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                      </svg>
                      <span className="text-xs font-bold tracking-tight text-slate-600">··{p.bank_account_id?.slice(-4) || "—"}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-xs font-bold text-slate-800 tabular-nums">
                        {new Date(p.created_at).toLocaleDateString("en-IN", { day: '2-digit', month: 'short' })}
                      </span>
                      <span className="text-[10px] font-medium text-slate-400 tabular-nums">
                        {new Date(p.created_at).toLocaleTimeString("en-IN", { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  </td>
                  <td className="px-8 py-5">
                    <div className="flex items-center gap-1">
                      <span className="text-xs font-bold text-slate-600">{p.attempt_count}</span>
                      <span className="text-[10px] font-medium text-slate-400">tries</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

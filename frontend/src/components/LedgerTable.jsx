import { formatINR } from "../api/client";

export default function LedgerTable({ entries }) {
  const credits = entries.filter((e) => e.entry_type === "credit").reduce((s, e) => s + e.amount_paise, 0);
  const debits  = entries.filter((e) => e.entry_type === "debit").reduce((s, e)  => s + e.amount_paise, 0);

  return (
    <div className="premium-card !p-0 overflow-hidden animate-slide-up">
      <div className="px-8 py-6 flex items-center justify-between border-b border-slate-100 bg-slate-50/30">
        <div>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">Activity Ledger</h2>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-1">{entries.length} Total Operations</p>
        </div>
        <div className="flex items-center gap-4 text-[10px] font-bold tracking-widest uppercase">
          <div className="flex flex-col items-end">
            <span className="text-slate-400 mb-0.5">Inflow</span>
            <span className="text-emerald-600">+{formatINR(credits)}</span>
          </div>
          <div className="w-px h-6 bg-slate-200" />
          <div className="flex flex-col items-end">
            <span className="text-slate-400 mb-0.5">Outflow</span>
            <span className="text-red-500">−{formatINR(debits)}</span>
          </div>
        </div>
      </div>

      {entries.length === 0 ? (
        <div className="py-20 text-center flex flex-col items-center justify-center">
          <div className="w-12 h-12 rounded-2xl bg-slate-50 flex items-center justify-center text-slate-300 mb-4">
            <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <p className="text-xs font-bold text-slate-400 uppercase tracking-[0.2em]">No Ledger Activity Yet</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-50/30">
                {["Type", "Amount", "Description", "Timestamp"].map((h) => (
                  <th key={h} className="px-8 py-4 text-left text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {entries.map((e, i) => (
                <tr
                  key={e.id}
                  className="group hover:bg-slate-50/50 transition-all duration-200 animate-fade-in"
                  style={{ animationDelay: `${i * 15}ms` }}
                >
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-xl flex items-center justify-center
                        ${e.entry_type === "credit" ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"}`}>
                        {e.entry_type === "credit" ? (
                          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                          </svg>
                        ) : (
                          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l7-7m0 0l7 7m-7-7v18" />
                          </svg>
                        )}
                      </div>
                      <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">{e.entry_type}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`text-sm font-bold tabular-nums tracking-tight
                      ${e.entry_type === "credit" ? "text-emerald-600" : "text-red-500"}`}>
                      {e.entry_type === "credit" ? "+" : "−"}{formatINR(e.amount_paise)}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <p className="text-xs font-medium text-slate-500 max-w-[200px] truncate">{e.description || "—"}</p>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-xs font-bold text-slate-800 tabular-nums">
                        {new Date(e.created_at).toLocaleDateString("en-IN", { day: '2-digit', month: 'short', year: 'numeric' })}
                      </span>
                      <span className="text-[10px] font-medium text-slate-400 tabular-nums">
                        {new Date(e.created_at).toLocaleTimeString("en-IN", { hour: '2-digit', minute: '2-digit', hour12: true })}
                      </span>
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

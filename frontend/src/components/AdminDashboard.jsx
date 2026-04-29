import { useEffect, useState } from "react";
import { api, formatINR } from "../api/client";

const STATUS = {
  pending:    { label: "Pending",    cls: "bg-amber-50 text-amber-600 border-amber-100",   dot: "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse" },
  processing: { label: "Processing", cls: "bg-blue-50 text-blue-600 border-blue-100",     dot: "bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.6)] animate-pulse" },
  completed:  { label: "Completed",  cls: "bg-emerald-50 text-emerald-600 border-emerald-100", dot: "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]" },
  failed:     { label: "Failed",     cls: "bg-red-50 text-red-600 border-red-100",         dot: "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]" },
};

function Badge({ status }) {
  const s = STATUS[status] || STATUS.pending;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold px-2 py-0.5 rounded-md border uppercase tracking-wider ${s.cls}`}>
      <span className={`w-1 h-1 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}

function Stat({ label, value, sub, valueClass = "text-slate-900", delay = 0 }) {
  return (
    <div className="premium-card animate-slide-up" style={{ animationDelay: `${delay}ms` }}>
      <p className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em] mb-3">{label}</p>
      <p className={`text-2xl font-extrabold tabular-nums tracking-tight ${valueClass}`}>{value}</p>
      {sub && <p className="text-[10px] font-bold text-slate-400 mt-2 uppercase tracking-wide">{sub}</p>}
    </div>
  );
}

export default function AdminDashboard({ merchants }) {
  const [payouts,   setPayouts]   = useState([]);
  const [balances,  setBalances]  = useState({});
  const [loading,   setLoading]   = useState(true);
  const [statusFilter, setFilter] = useState("all");

  useEffect(() => {
    async function load() {
      const results = await Promise.all(
        merchants.map(async (m) => {
          const [p, b] = await Promise.all([api.getPayouts(m.id), api.getBalance(m.id)]);
          return { m, payouts: p.ok ? p.data : [], balance: b.ok ? b.data : null };
        })
      );
      const balMap = {};
      const all = [];
      for (const r of results) {
        balMap[r.m.id] = { ...r.balance, name: r.m.name };
        r.payouts.forEach((p) => all.push({ ...p, merchantName: r.m.name }));
      }
      all.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setPayouts(all);
      setBalances(balMap);
      setLoading(false);
    }
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [merchants]);

  const settled   = payouts.filter((p) => p.status === "completed").reduce((s, p) => s + p.amount_paise, 0);
  const inFlight  = payouts.filter((p) => ["pending","processing"].includes(p.status)).reduce((s, p) => s + p.amount_paise, 0);
  const filtered  = statusFilter === "all" ? payouts : payouts.filter((p) => p.status === statusFilter);
  const cnt       = (s) => payouts.filter((p) => p.status === s).length;

  return (
    <div className="space-y-10 animate-fade-in">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold text-brand-500 uppercase tracking-[0.2em]">System Control</span>
            <div className="h-px w-8 bg-brand-500/20" />
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">System Overview</h1>
          <p className="text-sm font-medium text-slate-500 mt-1">Cross-merchant monitoring and global liquidity</p>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {loading ? (
          [...Array(4)].map((_, i) => <div key={i} className="h-32 glass-panel rounded-3xl animate-pulse" />)
        ) : (
          <>
            <Stat label="Total Merchants" value={merchants.length} sub="Active Entities" delay={0} />
            <Stat label="Global Payouts"  value={payouts.length} sub={`${cnt("completed")} Success`} delay={100} />
            <Stat label="Settled Volume" value={formatINR(settled)} valueClass="text-brand-600" sub="Total Processed" delay={200} />
            <Stat label="In-Flight"      value={formatINR(inFlight)} valueClass="text-amber-500" sub={`${cnt("pending") + cnt("processing")} Processing`} delay={300} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 items-start">
        {/* Merchant Liquidity */}
        <div className="premium-card !p-0 overflow-hidden xl:col-span-1">
          <div className="px-6 py-4 border-b border-slate-100 bg-slate-50/30">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-widest">Merchant Liquidity</h2>
          </div>
          <div className="divide-y divide-slate-50">
            {merchants.map((m) => {
              const b = balances[m.id];
              return (
                <div key={m.id} className="p-5 hover:bg-slate-50/50 transition-all group">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center text-[10px] font-bold">
                        {m.name[0]}
                      </div>
                      <span className="text-sm font-bold text-slate-800">{m.name}</span>
                    </div>
                    {b ? (
                      <span className="text-sm font-bold text-slate-900 tabular-nums">{formatINR(b.available_balance_paise)}</span>
                    ) : (
                      <div className="w-16 h-4 bg-slate-100 rounded-md animate-pulse" />
                    )}
                  </div>
                  {b?.held_balance_paise > 0 && (
                    <div className="flex items-center gap-2 ml-11">
                      <div className="w-1 h-1 rounded-full bg-amber-400" />
                      <span className="text-[10px] font-bold text-amber-500 uppercase tracking-wide">{formatINR(b.held_balance_paise)} Held</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* System Activity */}
        <div className="premium-card !p-0 overflow-hidden xl:col-span-2">
          <div className="px-8 py-6 border-b border-slate-100 bg-slate-50/30 flex items-center justify-between flex-wrap gap-4">
            <div>
              <h2 className="text-xs font-bold text-slate-900 uppercase tracking-widest">Live Activity Feed</h2>
            </div>
            <div className="flex bg-slate-100/50 p-1 rounded-xl">
              {["all","pending","processing","completed","failed"].map((s) => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition-all
                    ${statusFilter === s ? "bg-white text-slate-900 shadow-sm" : "text-slate-400 hover:text-slate-600"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50/30">
                  {["Merchant", "Amount", "Status", "Processed On"].map((h) => (
                    <th key={h} className="px-8 py-4 text-left text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filtered.slice(0, 15).map((p, i) => (
                  <tr key={p.id} className="group hover:bg-slate-50/50 transition-all duration-200">
                    <td className="px-8 py-4">
                      <span className="text-xs font-bold text-slate-800">{p.merchantName}</span>
                    </td>
                    <td className="px-8 py-4">
                      <span className="text-sm font-bold text-slate-900 tabular-nums tracking-tight">{formatINR(p.amount_paise)}</span>
                    </td>
                    <td className="px-8 py-4">
                      <Badge status={p.status} />
                    </td>
                    <td className="px-8 py-4">
                      <span className="text-[10px] font-bold text-slate-500 uppercase tabular-nums">
                        {new Date(p.created_at).toLocaleDateString("en-IN", { day: '2-digit', month: 'short' })} • {new Date(p.created_at).toLocaleTimeString("en-IN", { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="py-20 text-center text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">
                No transactions found for this filter
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Django Admin Quick Link */}
      <div className="glass-panel p-8 flex flex-col md:flex-row items-center justify-between gap-6 border-brand-500/10">
        <div className="flex items-center gap-6 text-center md:text-left">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/10 flex items-center justify-center text-brand-600">
            <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h3 className="text-lg font-extrabold text-slate-900 tracking-tight">Database Infrastructure</h3>
            <p className="text-sm font-medium text-slate-500 mt-1">Access Django ORM directly for manual ledger adjustments and audit logs.</p>
            <div className="mt-3 flex items-center gap-3">
              <span className="px-2 py-1 bg-slate-100 rounded text-[10px] font-bold text-slate-600 uppercase">admin</span>
              <span className="px-2 py-1 bg-slate-100 rounded text-[10px] font-bold text-slate-600 uppercase">admin123</span>
            </div>
          </div>
        </div>
        <a 
          href="http://localhost:8000/admin/" 
          target="_blank" 
          rel="noopener noreferrer"
          className="w-full md:w-auto px-8 py-4 bg-slate-900 text-white rounded-2xl text-[10px] font-bold uppercase tracking-widest hover:bg-slate-800 transition-all shadow-xl shadow-slate-200"
        >
          Open Control Panel →
        </a>
      </div>
    </div>
  );
}

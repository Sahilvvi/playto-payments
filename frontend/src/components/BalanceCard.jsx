import { useCountUp } from "../hooks/useCountUp";
import { formatINR } from "../api/client";

function AnimatedINR({ paise }) {
  const v = useCountUp(paise);
  return <>{formatINR(v)}</>;
}

export default function BalanceCard({ balance, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-40 glass-panel rounded-3xl animate-pulse" />
        ))}
      </div>
    );
  }
  if (!balance) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
      {/* Primary: Available */}
      <div className="relative group overflow-hidden md:col-span-2 rounded-3xl p-8 bg-brand-500 shadow-glow animate-slide-up border-none" style={{ animationDelay: "0ms" }}>
        {/* Animated Background Decor */}
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-white/10 rounded-full blur-3xl group-hover:scale-110 transition-transform duration-700" />
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-brand-400/20 rounded-full blur-3xl group-hover:scale-110 transition-transform duration-700" />
        
        <div className="relative z-10 h-full flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-white/15 backdrop-blur-md flex items-center justify-center">
                <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
                </svg>
              </div>
              <div>
                <span className="text-[10px] font-bold text-white/80 uppercase tracking-[0.2em]">Available Balance</span>
                <p className="text-sm font-bold text-white leading-none">Ready to Payout</p>
              </div>
            </div>
            <div className="px-3 py-1 rounded-full bg-white/15 backdrop-blur-md border border-white/10 flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)] animate-pulse" />
              <span className="text-[10px] font-bold text-white uppercase tracking-wider">Active</span>
            </div>
          </div>
          
          <div className="mt-auto">
            <h2 className="text-4xl md:text-5xl font-extrabold text-white tabular-nums tracking-tight">
              <AnimatedINR paise={balance.available_balance_paise} />
            </h2>
            <div className="flex items-center gap-2 mt-4 text-white/70 text-xs font-medium">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Standard settlement cycle (T+2) applied
            </div>
          </div>
        </div>
      </div>

      {/* Secondary Cards */}
      <div className="grid grid-cols-1 gap-6">
        {/* Held Card */}
        <div className="premium-card animate-slide-up" style={{ animationDelay: "100ms" }}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Funds Held</span>
            <div className={`w-2 h-2 rounded-full ${balance.held_balance_paise > 0 ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse" : "bg-slate-200"}`} />
          </div>
          <p className="text-2xl font-bold text-slate-900 tabular-nums">
            <AnimatedINR paise={balance.held_balance_paise} />
          </p>
          <p className="text-[10px] font-bold text-slate-500 mt-2 uppercase tracking-wide">In Processing</p>
        </div>

        {/* Total Earned Card */}
        <div className="premium-card animate-slide-up" style={{ animationDelay: "200ms" }}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-[0.2em]">Total Earned</span>
            <div className="w-2 h-2 rounded-full bg-brand-500 shadow-glow" />
          </div>
          <p className="text-2xl font-bold text-slate-900 tabular-nums">
            <AnimatedINR paise={balance.total_balance_paise} />
          </p>
          <p className="text-[10px] font-bold text-slate-500 mt-2 uppercase tracking-wide">Lifetime Credits</p>
        </div>
      </div>
    </div>
  );
}

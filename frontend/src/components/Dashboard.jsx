import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import BalanceCard from "./BalanceCard";
import PayoutForm from "./PayoutForm";
import PayoutHistory from "./PayoutHistory";
import LedgerTable from "./LedgerTable";

export default function Dashboard({ merchant }) {
  const [balance, setBalance] = useState(null);
  const [payouts, setPayouts] = useState([]);
  const [ledger,  setLedger]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab,     setTab]     = useState("payouts");

  const refresh = useCallback(async () => {
    const [b, p, l] = await Promise.all([
      api.getBalance(merchant.id),
      api.getPayouts(merchant.id),
      api.getLedger(merchant.id),
    ]);
    if (b.ok) { setBalance(b.data); setLoading(false); }
    if (p.ok) setPayouts(p.data);
    if (l.ok) setLedger(l.data);
  }, [merchant.id]);

  useEffect(() => {
    setBalance(null); setPayouts([]); setLedger([]); setLoading(true);
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Dashboard Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold text-brand-500 uppercase tracking-[0.2em]">Merchant Account</span>
            <div className="h-px w-8 bg-brand-500/20" />
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">{merchant.name}</h1>
          <p className="text-sm font-medium text-slate-500 mt-1">{merchant.email}</p>
        </div>
        
        <div className="flex items-center gap-3">
          {payouts.some((p) => ["pending","processing"].includes(p.status)) && (
            <div className="glass-panel px-4 py-2 rounded-2xl flex items-center gap-2.5 animate-pulse">
              <div className="w-1.5 h-1.5 rounded-full bg-brand-500 shadow-glow" />
              <span className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">Processing in Real-time</span>
            </div>
          )}
          <button 
            onClick={refresh}
            className="p-2.5 rounded-2xl glass-panel text-slate-400 hover:text-brand-500 hover:bg-brand-50 transition-all duration-300"
            title="Refresh Data"
          >
            <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      <BalanceCard balance={balance} loading={loading} />

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[380px,1fr] gap-8 items-start">
        {/* Left Column: Actions */}
        <div className="space-y-8">
          <PayoutForm
            merchantId={merchant.id}
            bankAccounts={merchant.bank_accounts}
            availablePaise={balance?.available_balance_paise ?? 0}
            onSuccess={refresh}
          />
        </div>

        {/* Right Column: Data Tables */}
        <div className="space-y-6">
          {/* Tabs Navigation */}
          <div className="flex items-center justify-between">
            <div className="glass-panel p-1 rounded-2xl flex gap-1 w-fit">
              {[["payouts","Payouts History"], ["ledger","Activity Ledger"]].map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`text-[11px] px-6 py-2 rounded-xl font-bold uppercase tracking-wider transition-all duration-300
                    ${tab === id 
                      ? "bg-slate-900 text-white shadow-lg shadow-slate-200" 
                      : "text-slate-500 hover:text-slate-700 hover:bg-slate-100"}`}
                >
                  {label}
                </button>
              ))}
            </div>
            
            <div className="hidden sm:flex items-center gap-2 text-slate-500">
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-[10px] font-bold uppercase tracking-widest">Auto-syncing</span>
            </div>
          </div>

          {/* Content Area */}
          <div className="animate-slide-up transition-all duration-500">
            {tab === "payouts"
              ? <PayoutHistory payouts={payouts} loading={loading && payouts.length === 0} />
              : <LedgerTable entries={ledger} />}
          </div>
        </div>
      </div>
    </div>
  );
}

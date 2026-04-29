import { useState, useEffect } from "react";
import { api } from "./api/client";
import { ToastProvider } from "./context/ToastContext";
import Sidebar from "./components/Sidebar";
import Dashboard from "./components/Dashboard";
import AdminDashboard from "./components/AdminDashboard";
import LedgerTable from "./components/LedgerTable";

function LedgerView({ merchant }) {
  const [entries, setEntries] = useState([]);
  useEffect(() => {
    api.getLedger(merchant.id).then(({ ok, data }) => ok && setEntries(data));
    const t = setInterval(() => api.getLedger(merchant.id).then(({ ok, data }) => ok && setEntries(data)), 5000);
    return () => clearInterval(t);
  }, [merchant.id]);
  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold text-brand-500 uppercase tracking-[0.2em]">Full Transaction Log</span>
            <div className="h-px w-8 bg-brand-500/20" />
          </div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Ledger</h1>
          <p className="text-sm font-medium text-slate-600 mt-1">{merchant.name} • source of truth records</p>
        </div>
      </div>
      <LedgerTable entries={entries} />
    </div>
  );
}

function MobileHeader({ onMenuOpen, selectedMerchant, view }) {
  const title = view === "admin" ? "Admin" : view === "ledger" ? "Ledger" : selectedMerchant?.name ?? "Dashboard";
  return (
    <header className="md:hidden fixed top-0 inset-x-0 z-50 h-16 bg-white/80 backdrop-blur-lg border-b border-slate-100 flex items-center px-6 gap-4">
      <button
        onClick={onMenuOpen}
        className="w-10 h-10 flex items-center justify-center rounded-xl bg-slate-50 text-slate-600 hover:bg-slate-100 transition-all"
      >
        <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
          <path d="M4 8h16M4 16h16"/>
        </svg>
      </button>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-slate-950 flex items-center justify-center shrink-0">
          <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth="2.5">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <span className="font-extrabold text-slate-900 text-sm tracking-tight truncate">{title}</span>
      </div>
    </header>
  );
}

function AppShell() {
  const [merchants, setMerchants]     = useState([]);
  const [selected,  setSelected]      = useState(null);
  const [view,      setView]          = useState("dashboard");
  const [status,    setStatus]        = useState("loading");
  const [mobileOpen, setMobileOpen]   = useState(false);

  useEffect(() => {
    api.getMerchants().then(({ ok, data }) => {
      const list = ok ? (data.results ?? data) : [];
      if (list.length) { setMerchants(list); setSelected(list[0]); setStatus("ok"); }
      else setStatus("error");
    }).catch(() => setStatus("error"));
  }, []);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="flex flex-col items-center gap-6">
          <div className="w-12 h-12 border-[3px] border-slate-100 border-t-brand-500 rounded-full animate-spin" />
          <div className="flex flex-col items-center gap-1">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Playto Payout</span>
            <span className="text-xs font-bold text-slate-900">Synchronizing Ledger...</span>
          </div>
        </div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen mesh-gradient flex items-center justify-center p-6">
        <div className="glass-panel p-10 max-w-sm w-full text-center border-red-500/10">
          <div className="w-14 h-14 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-6 text-red-500">
            <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-lg font-extrabold text-slate-900 tracking-tight mb-2">Connectivity Failure</h2>
          <p className="text-xs font-medium text-slate-500 mb-8 leading-relaxed">
            Unable to connect to the Payout Engine. Please ensure the backend is running and seeded.
          </p>
          <div className="space-y-2">
            <code className="block bg-slate-950 text-slate-300 text-[10px] p-3 rounded-xl font-bold">python manage.py runserver</code>
            <code className="block bg-slate-950 text-slate-300 text-[10px] p-3 rounded-xl font-bold">python manage.py seed</code>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen mesh-gradient text-slate-900 selection:bg-brand-100 selection:text-brand-700">
      <MobileHeader
        onMenuOpen={() => setMobileOpen(true)}
        selectedMerchant={selected}
        view={view}
      />

      <Sidebar
        active={view}
        onChange={setView}
        merchants={merchants}
        selectedMerchant={selected}
        onMerchantChange={(m) => { setSelected(m); setView("dashboard"); }}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      <main className="flex-1 relative z-10">
        <div className="w-full px-6 lg:px-10 pt-24 pb-12 md:pt-10">
          <div className="max-w-7xl">
            {view === "admin"     && <AdminDashboard merchants={merchants} />}
            {view === "ledger"    && selected && <LedgerView key={selected.id} merchant={selected} />}
            {view === "dashboard" && selected && <Dashboard  key={selected.id} merchant={selected} />}
          </div>
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return <ToastProvider><AppShell /></ToastProvider>;
}

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: (
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
    </svg>
  )},
  { id: "ledger", label: "Ledger", icon: (
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )},
  { id: "admin", label: "Admin Panel", icon: (
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  )},
];

function SidebarContent({ active, onChange, merchants, selectedMerchant, onMerchantChange, onClose }) {
  return (
    <div className="flex flex-col h-full bg-slate-950 text-slate-400">
      {/* Brand */}
      <div className="px-6 py-8">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-brand-400 flex items-center justify-center shadow-glow">
            <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="white" strokeWidth="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <h1 className="font-bold text-white text-base tracking-tight leading-none">Playto</h1>
            <p className="text-[10px] text-slate-300 font-bold mt-1 tracking-wider uppercase">Payout Engine</p>
          </div>
        </div>
      </div>

      <div className="flex-1 px-4 overflow-y-auto space-y-8 scrollbar-hide">
        {/* Merchant Select */}
        <section>
          <h2 className="px-2 mb-3 text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em]">Accounts</h2>
          <div className="space-y-1">
            {merchants.map((m) => {
              const isActive = selectedMerchant?.id === m.id && active !== "admin";
              return (
                <button
                  key={m.id}
                  onClick={() => { onMerchantChange(m); onChange("dashboard"); onClose?.(); }}
                  className={`w-full group flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200
                    ${isActive 
                      ? "bg-white/10 text-white shadow-sm" 
                      : "hover:bg-white/5 hover:text-slate-200 text-slate-300"}`}
                >
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold transition-all duration-200
                    ${isActive ? "bg-brand-500 text-white shadow-glow" : "bg-slate-900 text-slate-600 group-hover:bg-slate-800"}`}>
                    {m.name[0]}
                  </div>
                  <span className="text-xs font-semibold truncate tracking-tight">{m.name}</span>
                  {isActive && <div className="ml-auto w-1 h-1 rounded-full bg-brand-400 shadow-glow" />}
                </button>
              );
            })}
          </div>
        </section>

        {/* Navigation */}
        <section>
          <h2 className="px-2 mb-3 text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em]">Menu</h2>
          <div className="space-y-1">
            {NAV.map((item) => {
              const isActive = active === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => { onChange(item.id); onClose?.(); }}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200
                    ${isActive 
                      ? "bg-brand-500 text-white shadow-glow" 
                      : "hover:bg-white/5 hover:text-slate-200 text-slate-300"}`}
                >
                  <span className={isActive ? "text-white" : "text-slate-300 group-hover:text-slate-200"}>
                    {item.icon}
                  </span>
                  <span className="text-xs font-semibold tracking-tight">{item.label}</span>
                </button>
              );
            })}
          </div>
        </section>
      </div>

      {/* Footer */}
      <div className="p-4 mt-auto">
        <a
          href="http://localhost:8000/admin/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 w-full py-3 rounded-xl border border-slate-800 text-[10px] font-bold text-slate-500 hover:text-slate-300 hover:bg-white/5 transition-all"
        >
          <svg width="12" height="12" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          SYSTEM ADMIN
        </a>
      </div>
    </div>
  );
}

export default function Sidebar({ active, onChange, merchants, selectedMerchant, onMerchantChange, mobileOpen, onCloseMobile }) {
  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-[50] bg-slate-950/80 backdrop-blur-md md:hidden animate-fade-in"
          onClick={onCloseMobile}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          fixed top-0 left-0 z-[60] h-screen w-72 flex flex-col
          transform transition-transform duration-300 ease-in-out shadow-2xl
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0 md:sticky md:top-0 md:w-64 md:shrink-0 md:shadow-none
        `}
      >
        <SidebarContent
          active={active}
          onChange={onChange}
          merchants={merchants}
          selectedMerchant={selectedMerchant}
          onMerchantChange={onMerchantChange}
          onClose={onCloseMobile}
        />
      </aside>
    </>
  );
}

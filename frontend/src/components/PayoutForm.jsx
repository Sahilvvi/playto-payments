import { useState } from "react";
import { api, generateUUID, formatINR } from "../api/client";
import { useToast } from "../context/ToastContext";

const QUICK = [500, 1000, 2500, 5000];

export default function PayoutForm({ merchantId, bankAccounts, availablePaise, onSuccess }) {
  const [amount, setAmount]       = useState("");
  const [bankId, setBankId]       = useState(bankAccounts[0]?.id || "");
  const [loading, setLoading]     = useState(false);
  const toast = useToast();

  const rupees   = parseFloat(amount) || 0;
  const paise    = Math.round(rupees * 100);
  const pct      = availablePaise > 0 ? Math.min((paise / availablePaise) * 100, 100) : 0;
  const overdrawn = paise > availablePaise && rupees > 0;

  async function submit(e) {
    e.preventDefault();
    if (!paise || paise <= 0) { toast.add("Enter a valid amount", "warning"); return; }
    if (paise > availablePaise) { toast.add(`Max available: ${formatINR(availablePaise)}`, "error"); return; }

    setLoading(true);
    const { ok, status, data } = await api.createPayout(merchantId, generateUUID(), {
      amount_paise: paise,
      bank_account_id: bankId,
    });
    setLoading(false);

    if (ok) {
      setAmount("");
      toast.add(`Payout of ${formatINR(paise)} submitted`, "success");
      onSuccess(data);
    } else {
      toast.add(data?.error || `Error ${status}`, "error");
    }
  }

  return (
    <form onSubmit={submit} className="premium-card animate-slide-up flex flex-col h-fit">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-xl bg-brand-50 flex items-center justify-center text-brand-600">
          <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </div>
        <div>
          <h2 className="text-sm font-bold text-slate-900 tracking-tight">Request Payout</h2>
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Withdrawal Action</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* Amount Input */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Amount to Send</label>
            <span className="text-[10px] font-bold text-slate-400 tabular-nums">INR</span>
          </div>
          
          <div className={`relative group flex items-center border-2 rounded-2xl transition-all duration-300
            ${overdrawn 
              ? "border-red-200 bg-red-50/30" 
              : "border-slate-100 bg-slate-50/30 focus-within:border-brand-500 focus-within:bg-white focus-within:shadow-glow"}`}>
            <span className="pl-4 pr-2 text-slate-400 text-lg font-bold select-none">₹</span>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full py-4 pr-4 text-xl font-bold text-slate-900 bg-transparent outline-none tabular-nums placeholder:text-slate-200"
              required
            />
          </div>

          {/* Availability Gauge */}
          <div className="mt-3">
            <div className="flex justify-between items-center mb-1.5">
              <span className={`text-[10px] font-bold uppercase tracking-wide ${overdrawn ? "text-red-500" : "text-slate-400"}`}>
                {overdrawn ? "Over Limit" : `Available: ${formatINR(availablePaise)}`}
              </span>
              <span className="text-[10px] font-bold text-slate-400 tabular-nums">{pct.toFixed(0)}%</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out 
                  ${overdrawn ? "bg-red-400" : "bg-gradient-to-r from-brand-500 to-cyan-400"}`}
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </section>

        {/* Quick Select Buttons */}
        <div className="grid grid-cols-4 gap-2">
          {QUICK.map((r) => {
            const isDisabled = r * 100 > availablePaise;
            const isSelected = amount === String(r);
            return (
              <button
                key={r}
                type="button"
                disabled={isDisabled}
                onClick={() => setAmount(String(r))}
                className={`py-2 rounded-xl text-[10px] font-bold transition-all duration-200 border-2
                  ${isSelected
                    ? "bg-brand-500 border-brand-500 text-white shadow-glow"
                    : "bg-white border-slate-100 text-slate-500 hover:border-slate-200 disabled:opacity-30 disabled:hover:border-slate-100"
                  }`}
              >
                ₹{r >= 1000 ? `${r/1000}k` : r}
              </button>
            );
          })}
        </div>

        {/* Destination Account */}
        <section>
          <label className="block text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Destination Bank</label>
          <div className="relative group">
            <select
              value={bankId}
              onChange={(e) => setBankId(e.target.value)}
              className="w-full border-2 border-slate-100 bg-slate-50/30 rounded-2xl px-4 py-3.5 text-xs font-bold text-slate-800
                focus:outline-none focus:border-brand-500 focus:bg-white focus:shadow-glow transition-all appearance-none pr-10"
              required
            >
              {bankAccounts.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.account_holder_name} (..{b.account_number.slice(-4)})
                </option>
              ))}
            </select>
            <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-slate-400">
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>
        </section>

        {/* Action Button */}
        <button
          type="submit"
          disabled={loading || overdrawn || !amount}
          className="w-full group relative overflow-hidden bg-brand-500 disabled:bg-slate-100 disabled:text-slate-400
            text-white font-bold py-4 rounded-2xl text-xs uppercase tracking-widest transition-all duration-300
            shadow-glow hover:shadow-brand-500/40 hover:-translate-y-0.5 active:translate-y-0 disabled:shadow-none disabled:translate-y-0"
        >
          <div className="relative z-10 flex items-center justify-center gap-2">
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
            {loading ? "Processing..." : "Initiate Payout"}
          </div>
          <div className="absolute inset-0 bg-gradient-to-r from-brand-600 to-brand-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </button>
      </div>
    </form>
  );
}

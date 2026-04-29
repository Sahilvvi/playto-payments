import { createContext, useContext, useState, useCallback } from "react";

const ToastContext = createContext(null);
let _id = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const add = useCallback((message, type = "info", duration = 4000) => {
    const id = ++_id;
    setToasts((p) => [...p, { id, message, type }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), duration);
  }, []);

  const remove = useCallback((id) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  return (
    <ToastContext.Provider value={{ add, remove }}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            onClick={() => remove(t.id)}
            className={`animate-toast pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg
              border text-sm font-medium cursor-pointer max-w-sm
              ${t.type === "success" ? "bg-white border-emerald-200 text-gray-800" :
                t.type === "error"   ? "bg-white border-red-200 text-gray-800" :
                t.type === "warning" ? "bg-white border-amber-200 text-gray-800" :
                                       "bg-white border-gray-200 text-gray-800"}`}
          >
            <span className={`mt-0.5 w-4 h-4 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0
              ${t.type === "success" ? "bg-emerald-500" :
                t.type === "error"   ? "bg-red-500" :
                t.type === "warning" ? "bg-amber-500" : "bg-blue-500"}`}>
              {t.type === "success" ? "✓" : t.type === "error" ? "✕" : "!"}
            </span>
            <span className="leading-snug">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

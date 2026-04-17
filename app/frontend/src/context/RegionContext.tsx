import { createContext, useContext, useState, useEffect, ReactNode } from "react";

export interface MarketInfo {
  code: string;
  name: string;
  flag: string;
  market_name: string;
  currency: string;
  data_available: string; // "true" | "false" (from API)
}

interface RegionContextValue {
  market: string;
  setMarket: (code: string) => void;
  markets: MarketInfo[];
  activeMarket: MarketInfo | null;
}

export const RegionContext = createContext<RegionContextValue>({
  market: "AU",
  setMarket: () => {},
  markets: [],
  activeMarket: null,
});

export function RegionProvider({ children }: { children: ReactNode }) {
  const [market, setMarketState] = useState<string>(
    () => localStorage.getItem("compliance_market") || "AU"
  );
  const [markets, setMarkets] = useState<MarketInfo[]>([]);

  useEffect(() => {
    fetch("/api/regions")
      .then((r) => r.ok ? r.json() : Promise.reject())
      .then((d) => setMarkets(d.markets ?? []))
      .catch(() => {});
  }, []);

  const setMarket = (code: string) => {
    setMarketState(code);
    localStorage.setItem("compliance_market", code);
  };

  const activeMarket = markets.find((m) => m.code === market) ?? null;

  return (
    <RegionContext.Provider value={{ market, setMarket, markets, activeMarket }}>
      {children}
    </RegionContext.Provider>
  );
}

export function useRegion() {
  return useContext(RegionContext);
}

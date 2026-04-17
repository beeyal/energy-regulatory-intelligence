import { useState, useCallback } from "react";

export type Language = "en" | "ja" | "ko" | "th";

export const LANGUAGES: { code: Language; label: string; flag: string; name: string }[] = [
  { code: "en", label: "EN", flag: "🇦🇺", name: "English" },
  { code: "ja", label: "JA", flag: "🇯🇵", name: "日本語" },
  { code: "ko", label: "KO", flag: "🇰🇷", name: "한국어" },
  { code: "th", label: "TH", flag: "🇹🇭", name: "ภาษาไทย" },
];

// Core UI string translations
const TRANSLATIONS: Record<Language, Record<string, string>> = {
  en: {
    appTitle: "Regulatory Intelligence Command Center",
    appSubtitle: "AI-powered compliance monitoring — CER, AEMO, AER, AEMC",
    tabRisk: "Risk Overview",
    tabMarkets: "Markets",
    tabHorizon: "Horizon",
    tabGaps: "Compliance Insights",
    tabEmissions: "Emissions",
    tabForecast: "Safeguard Forecast",
    tabNotices: "Market Notices",
    tabEnforcement: "Enforcement",
    tabObligations: "Obligations",
    tabBenchmark: "Benchmarking",
    tabImpact: "Impact Analysis",
    tabEsg: "ESG Disclosure",
    tabExtract: "Obligation Extractor",
    btnHelp: "? Help",
    btnLight: "☀ Light",
    btnDark: "◑ Dark",
    labelEmissions: "emissions",
    labelNotices: "notices",
    labelEnforcement: "enforcement",
    labelObligations: "obligations",
  },
  ja: {
    appTitle: "規制インテリジェンス・コマンドセンター",
    appSubtitle: "AI搭載コンプライアンス監視 — CER, AEMO, AER, AEMC",
    tabRisk: "リスク概要",
    tabMarkets: "市場",
    tabHorizon: "ホライズン",
    tabGaps: "コンプライアンス分析",
    tabEmissions: "排出量",
    tabForecast: "セーフガード予測",
    tabNotices: "市場通知",
    tabEnforcement: "執行",
    tabObligations: "義務",
    tabBenchmark: "ベンチマーク",
    tabImpact: "影響分析",
    tabEsg: "ESG開示",
    tabExtract: "義務抽出",
    btnHelp: "? ヘルプ",
    btnLight: "☀ ライト",
    btnDark: "◑ ダーク",
    labelEmissions: "排出量",
    labelNotices: "通知",
    labelEnforcement: "執行",
    labelObligations: "義務",
  },
  ko: {
    appTitle: "규제 인텔리전스 커맨드 센터",
    appSubtitle: "AI 기반 컴플라이언스 모니터링 — CER, AEMO, AER, AEMC",
    tabRisk: "리스크 개요",
    tabMarkets: "시장",
    tabHorizon: "호라이즌",
    tabGaps: "컴플라이언스 분석",
    tabEmissions: "배출량",
    tabForecast: "세이프가드 예측",
    tabNotices: "시장 공지",
    tabEnforcement: "집행",
    tabObligations: "의무사항",
    tabBenchmark: "벤치마킹",
    tabImpact: "영향 분석",
    tabEsg: "ESG 공시",
    tabExtract: "의무 추출",
    btnHelp: "? 도움말",
    btnLight: "☀ 라이트",
    btnDark: "◑ 다크",
    labelEmissions: "배출량",
    labelNotices: "공지",
    labelEnforcement: "집행",
    labelObligations: "의무",
  },
  th: {
    appTitle: "ศูนย์บัญชาการข่าวกรองด้านกฎระเบียบ",
    appSubtitle: "การติดตามการปฏิบัติตามกฎระเบียบด้วย AI — CER, AEMO, AER, AEMC",
    tabRisk: "ภาพรวมความเสี่ยง",
    tabMarkets: "ตลาด",
    tabHorizon: "ขอบฟ้า",
    tabGaps: "ข้อมูลเชิงลึก",
    tabEmissions: "การปล่อยก๊าซ",
    tabForecast: "การพยากรณ์",
    tabNotices: "ประกาศตลาด",
    tabEnforcement: "การบังคับใช้",
    tabObligations: "ข้อผูกพัน",
    tabBenchmark: "การเปรียบเทียบ",
    tabImpact: "การวิเคราะห์ผลกระทบ",
    tabEsg: "การเปิดเผย ESG",
    tabExtract: "การดึงข้อผูกพัน",
    btnHelp: "? ช่วยเหลือ",
    btnLight: "☀ สว่าง",
    btnDark: "◑ มืด",
    labelEmissions: "การปล่อยก๊าซ",
    labelNotices: "ประกาศ",
    labelEnforcement: "การบังคับใช้",
    labelObligations: "ข้อผูกพัน",
  },
};

const LANG_KEY = "app_language";

export function useLanguage() {
  const [lang, setLangState] = useState<Language>(() => {
    const stored = localStorage.getItem(LANG_KEY);
    return (stored as Language) || "en";
  });

  const setLang = useCallback((l: Language) => {
    setLangState(l);
    localStorage.setItem(LANG_KEY, l);
  }, []);

  const t = useCallback((key: string): string => {
    return TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en[key] ?? key;
  }, [lang]);

  return { lang, setLang, t };
}

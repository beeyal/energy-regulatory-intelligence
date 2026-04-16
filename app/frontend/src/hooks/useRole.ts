import { useState } from "react";

export type UserRole = "cro" | "cfo" | "general_counsel" | "head_reg_affairs" | "compliance_analyst" | null;

const ROLE_KEY = "compliance_user_role";

export const ROLE_LABELS: Record<NonNullable<UserRole>, string> = {
  cro: "CRO",
  cfo: "CFO",
  general_counsel: "General Counsel",
  head_reg_affairs: "Head of Reg Affairs",
  compliance_analyst: "Compliance Analyst",
};

export const ROLE_CHIPS: Record<NonNullable<UserRole>, string[]> = {  // exported for ChatPanel dynamic substitution
  cro: [
    "What are our top 3 regulatory risks this quarter?",
    "Which regulators have escalated enforcement recently?",
    "Summarise Safeguard exposure for AGL",
    "Show repeat offenders in AER enforcement data",
  ],
  cfo: [
    "What is our total penalty exposure?",
    "Which companies will breach Safeguard baseline by 2027?",
    "Show AER enforcement penalties in the last 12 months",
    "Top emitters and their Scope 1 trajectory",
  ],
  general_counsel: [
    "Show AER enforcement actions in the last 12 months",
    "Which obligations carry penalties over $1M?",
    "List companies with 3 or more enforcement actions",
    "Show court proceedings and enforceable undertakings",
  ],
  head_reg_affairs: [
    "Show all CER obligations due this quarter",
    "Market notices with NON-CONFORMANCE type",
    "What AEMC obligations are in the register?",
    "Show Critical and High risk obligations for AEMO",
  ],
  compliance_analyst: [
    "List all Critical obligations for AEMO",
    "Show enforcement actions by breach type",
    "What are the NGER reporting obligations?",
    "Show recent non-conformance market notices",
  ],
};

const DEFAULT_CHIPS = [
  "Who are the top 10 emitters in the electricity sector?",
  "Show me recent AEMO non-conformance notices",
  "Which companies have been fined the most by the AER?",
  "What are the key obligations under NER Chapter 7?",
];

export function useRole() {
  const [role, setRoleState] = useState<UserRole>(() => {
    return (localStorage.getItem(ROLE_KEY) as UserRole) ?? null;
  });

  const setRole = (r: UserRole) => {
    if (r) localStorage.setItem(ROLE_KEY, r);
    else localStorage.removeItem(ROLE_KEY);
    setRoleState(r);
  };

  return { role, setRole };
}

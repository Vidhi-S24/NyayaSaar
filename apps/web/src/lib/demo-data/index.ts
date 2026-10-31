/**
 * Demo data fixtures for NyayaSaar Stage 2.
 *
 * IMPORTANT: These are clearly labelled development fixtures.
 * They are NOT real legal research results, real case citations,
 * or verified legal authorities. Any names resembling real cases
 * are coincidental. Professional verification is always required.
 */

export type CaseStatus = "active" | "review" | "closed" | "archived";
export type DocumentType = "petition" | "judgment" | "affidavit" | "order" | "contract" | "statute" | "brief";
export type Priority = "high" | "medium" | "low";

export interface DemoCase {
  id: string;
  title: string;
  caseNumber: string;
  court: string;
  status: CaseStatus;
  priority: Priority;
  documentsCount: number;
  lastActivity: string;
  createdAt: string;
  summary: string;
  tags: string[];
  issues: string[];
}

export interface DemoDocument {
  id: string;
  caseId: string;
  name: string;
  type: DocumentType;
  size: string;
  uploadedAt: string;
  pages: number;
  status: "processed" | "processing" | "pending" | "error";
}

export interface DemoActivity {
  id: string;
  type: "document_uploaded" | "analysis_complete" | "case_created" | "report_saved" | "contradiction_found";
  caseId: string;
  caseTitle: string;
  description: string;
  timestamp: string;
  user: string;
}

export interface DemoAuthority {
  id: string;
  citation: string;
  court: string;
  year: number;
  summary: string;
  relevance: "high" | "medium" | "low";
  treatment: "supporting" | "distinguishing" | "neutral";
  isDemo: true; // Always true — these are not verified authorities
}

export const DEMO_CASES: DemoCase[] = [
  {
    id: "case-001",
    title: "Sharma vs. Municipal Corporation — Land Acquisition Dispute",
    caseNumber: "WP/4521/2024",
    court: "High Court of Delhi",
    status: "active",
    priority: "high",
    documentsCount: 12,
    lastActivity: "2 hours ago",
    createdAt: "2024-10-15",
    summary:
      "Challenge to land acquisition proceedings under the Right to Fair Compensation Act. Petitioner alleges procedural irregularities and inadequate compensation.",
    tags: ["Land Acquisition", "Constitutional", "Compensation"],
    issues: [
      "Validity of Section 4 notification",
      "Adequacy of compensation offered",
      "Violation of natural justice principles",
      "Delay in award proceedings",
    ],
  },
  {
    id: "case-002",
    title: "Patel Industries vs. State of Gujarat — Contract Breach",
    caseNumber: "CS/892/2024",
    court: "Commercial Court, Ahmedabad",
    status: "review",
    priority: "medium",
    documentsCount: 8,
    lastActivity: "1 day ago",
    createdAt: "2024-09-20",
    summary:
      "Commercial dispute arising from alleged breach of government supply contract. Respondent disputes liability and invokes force majeure clauses.",
    tags: ["Contract", "Commercial", "Force Majeure"],
    issues: [
      "Interpretation of force majeure clause",
      "Quantum of damages claimed",
      "Applicability of liquidated damages",
    ],
  },
  {
    id: "case-003",
    title: "Krishnamurthy Family Trust — Succession Dispute",
    caseNumber: "TS/156/2024",
    court: "City Civil Court, Bengaluru",
    status: "active",
    priority: "medium",
    documentsCount: 21,
    lastActivity: "3 days ago",
    createdAt: "2024-08-01",
    summary:
      "Complex succession dispute involving multiple claimants to a family trust. Issues of Hindu Succession Act applicability and trust deed interpretation.",
    tags: ["Succession", "Trust", "Hindu Law"],
    issues: [
      "Validity of trust deed amendments",
      "Rights of adopted heirs",
      "Tax implications of succession",
    ],
  },
  {
    id: "case-004",
    title: "Tech Ventures Pvt. Ltd. — IP Infringement",
    caseNumber: "CS(COMM)/1203/2024",
    court: "Delhi High Court (Commercial Division)",
    status: "active",
    priority: "high",
    documentsCount: 6,
    lastActivity: "5 hours ago",
    createdAt: "2024-10-22",
    summary:
      "Suit for trademark infringement and passing off. Plaintiff seeks injunction against use of confusingly similar trade dress in software products.",
    tags: ["Intellectual Property", "Trademark", "Injunction"],
    issues: [
      "Likelihood of consumer confusion",
      "Prior use and registration",
      "Balance of convenience for interim relief",
    ],
  },
  {
    id: "case-005",
    title: "Mehta vs. Mehta — Matrimonial Property Division",
    caseNumber: "HMP/334/2024",
    court: "Family Court, Mumbai",
    status: "closed",
    priority: "low",
    documentsCount: 14,
    lastActivity: "2 weeks ago",
    createdAt: "2024-06-10",
    summary:
      "Matrimonial dispute involving division of jointly acquired property and maintenance claims. Parties reached partial settlement; remaining issues before court.",
    tags: ["Family Law", "Property", "Maintenance"],
    issues: ["Division of jointly acquired flat", "Monthly maintenance quantum", "Children's education expenses"],
  },
];

export const DEMO_DOCUMENTS: DemoDocument[] = [
  { id: "doc-001", caseId: "case-001", name: "Writ Petition — Sharma vs MCD.pdf", type: "petition", size: "2.4 MB", uploadedAt: "2024-10-15", pages: 38, status: "processed" },
  { id: "doc-002", caseId: "case-001", name: "Land Acquisition Notification S4.pdf", type: "order", size: "0.8 MB", uploadedAt: "2024-10-15", pages: 6, status: "processed" },
  { id: "doc-003", caseId: "case-001", name: "Compensation Award Order.pdf", type: "order", size: "1.1 MB", uploadedAt: "2024-10-16", pages: 12, status: "processed" },
  { id: "doc-004", caseId: "case-001", name: "Respondent Counter Affidavit.pdf", type: "affidavit", size: "3.2 MB", uploadedAt: "2024-10-20", pages: 45, status: "processing" },
  { id: "doc-005", caseId: "case-002", name: "Government Supply Contract 2022.pdf", type: "contract", size: "1.9 MB", uploadedAt: "2024-09-20", pages: 24, status: "processed" },
  { id: "doc-006", caseId: "case-002", name: "Breach Notice — Patel Industries.pdf", type: "order", size: "0.4 MB", uploadedAt: "2024-09-21", pages: 4, status: "processed" },
  { id: "doc-007", caseId: "case-004", name: "Trademark Registration Certificate.pdf", type: "order", size: "0.6 MB", uploadedAt: "2024-10-22", pages: 3, status: "processed" },
  { id: "doc-008", caseId: "case-004", name: "Plaint — IP Infringement Suit.pdf", type: "petition", size: "4.1 MB", uploadedAt: "2024-10-22", pages: 62, status: "pending" },
];

export const DEMO_ACTIVITY: DemoActivity[] = [
  {
    id: "act-001",
    type: "contradiction_found",
    caseId: "case-001",
    caseTitle: "Sharma vs. Municipal Corporation",
    description: "2 date inconsistencies detected between notification and award documents",
    timestamp: "2 hours ago",
    user: "System",
  },
  {
    id: "act-002",
    type: "document_uploaded",
    caseId: "case-001",
    caseTitle: "Sharma vs. Municipal Corporation",
    description: "Respondent Counter Affidavit uploaded (45 pages, processing)",
    timestamp: "2 hours ago",
    user: "You",
  },
  {
    id: "act-003",
    type: "analysis_complete",
    caseId: "case-004",
    caseTitle: "Tech Ventures Pvt. Ltd.",
    description: "Case Intelligence analysis completed — 4 key legal issues identified",
    timestamp: "5 hours ago",
    user: "System",
  },
  {
    id: "act-004",
    type: "report_saved",
    caseId: "case-002",
    caseTitle: "Patel Industries vs. State of Gujarat",
    description: "Force majeure clause analysis report saved",
    timestamp: "1 day ago",
    user: "You",
  },
  {
    id: "act-005",
    type: "case_created",
    caseId: "case-004",
    caseTitle: "Tech Ventures Pvt. Ltd.",
    description: "New case workspace created",
    timestamp: "2 days ago",
    user: "You",
  },
];

// Demo authorities — NOT real verified legal research
export const DEMO_AUTHORITIES: DemoAuthority[] = [
  {
    id: "auth-001",
    citation: "[DEMO] Illustrative Case A v. State (2019) — fictional fixture",
    court: "Supreme Court [DEMO]",
    year: 2019,
    summary: "This is a clearly labelled demo fixture. It is not a real legal authority and must not be cited in legal proceedings.",
    relevance: "high",
    treatment: "supporting",
    isDemo: true,
  },
  {
    id: "auth-002",
    citation: "[DEMO] Municipal Board v. Residents (2021) — fictional fixture",
    court: "High Court [DEMO]",
    year: 2021,
    summary: "This is a clearly labelled demo fixture. It is not a real legal authority and must not be cited in legal proceedings.",
    relevance: "medium",
    treatment: "distinguishing",
    isDemo: true,
  },
];

export const DEMO_STATS = {
  activeCases: 3,
  documentsProcessed: 41,
  reportsGenerated: 7,
  contradictionsFound: 5,
};


/**
 * Legal pages. Have them reviewed by counsel for your jurisdiction before launch; the entity
 * name, address and contact emails come from NEXT_PUBLIC_* settings (see lib/marketing.ts).
 */
import { SITE } from "@/lib/marketing";

export type LegalSection = { heading: string; body: (string | string[])[] };
export type LegalDocument = { slug: string; title: string; summary: string; updated: string; sections: LegalSection[] };

const UPDATED = "2026-10-01";
const N = SITE.name;
const E = SITE.legalEntity;

export const LEGAL_DOCUMENTS: LegalDocument[] = [
  {
    slug: "terms",
    title: "Terms of Service",
    summary: `The agreement between you and ${E} for using ${N}.`,
    updated: UPDATED,
    sections: [
      {
        heading: "1. Who we are and what these terms cover",
        body: [
          `${N} is provided by ${E} (${SITE.legalAddress}). These terms apply to your use of the ${N} website, web application and API (the "Service"). By creating an account you agree to them on behalf of yourself and the organisation you represent.`,
        ],
      },
      {
        heading: "2. Your account",
        body: [
          "You must give accurate information, keep your credentials secure and tell us promptly about any unauthorised use. Workspace owners control who can access their workspace and are responsible for their members' use of it.",
        ],
      },
      {
        heading: "3. Acceptable use",
        body: [
          "You must follow our Acceptable Use Policy and all laws that apply to your outreach, including data protection and electronic marketing rules such as the GDPR, UK GDPR, PECR and CAN-SPAM. You are the controller of the personal data you add to the Service and are responsible for having a lawful basis to process it.",
        ],
      },
      {
        heading: "4. Plans, payment and trials",
        body: [
          "Paid plans are billed in advance through our payment provider and renew automatically until cancelled. You can cancel at any time; access continues until the end of the paid period. Trials convert to the free plan unless you choose a paid plan. Fees exclude applicable taxes.",
          "If a payment fails we may limit sending after a grace period until it is resolved.",
        ],
      },
      {
        heading: "5. Your data",
        body: [
          "You keep all rights to the data you put into the Service. We process it only to provide the Service, as described in our Data Processing Agreement and Privacy Policy. You can export your data at any time and we delete it after your account is closed, subject to legal retention requirements.",
        ],
      },
      {
        heading: "6. Third-party services",
        body: [
          "You may connect your own email, search, enrichment and AI providers. Your use of those services is governed by your agreements with them, and you are responsible for the credentials you provide.",
        ],
      },
      {
        heading: "7. Availability and changes",
        body: [
          "We work to keep the Service available and secure but do not guarantee it will be uninterrupted. We may change or improve features; we will give reasonable notice of changes that materially reduce the Service.",
        ],
      },
      {
        heading: "8. Suspension and termination",
        body: [
          "We may suspend sending or accounts that breach these terms or the Acceptable Use Policy, or that put the Service or its users at risk (for example, high bounce or complaint rates). You may close your account at any time from your settings.",
        ],
      },
      {
        heading: "9. Liability",
        body: [
          "To the extent permitted by law, the Service is provided \"as is\", and our total liability for any claim is limited to the fees you paid in the twelve months before the claim. We are not liable for indirect or consequential losses. Nothing limits liability that cannot be limited by law.",
        ],
      },
      {
        heading: "10. General",
        body: [
          `These terms are governed by the laws of the jurisdiction where ${E} is established. If we update them we will post the new version here and, for material changes, tell you in advance. Questions: ${SITE.contactEmail}.`,
        ],
      },
    ],
  },
  {
    slug: "privacy",
    title: "Privacy Policy",
    summary: "How we handle personal data about our customers, website visitors and the people our customers contact.",
    updated: UPDATED,
    sections: [
      {
        heading: "1. Our role",
        body: [
          `For account, billing and website data, ${E} is the controller. For the lead and contact data that customers add to their workspaces, the customer is the controller and we act as their processor under our Data Processing Agreement.`,
        ],
      },
      {
        heading: "2. What we collect",
        body: [
          [
            "Account data: name, email address, password hash, two-factor settings, workspace memberships.",
            "Billing data: plan, invoices and payment status (card details are held by our payment provider, not by us).",
            "Usage data: sign-ins, security events, device and IP address for active sessions, audit log entries.",
            "Website data: essential cookies and, only with your consent, analytics about pages visited.",
            "Messages you send us through the contact form or by email.",
          ],
        ],
      },
      {
        heading: "3. Why we use it",
        body: [
          [
            "To provide and secure the Service (contract and legitimate interests).",
            "To bill you and keep financial records (contract and legal obligation).",
            "To improve the product using aggregated usage data (legitimate interests, or consent for analytics cookies).",
            "To send service messages such as verification, security and billing emails (contract).",
          ],
        ],
      },
      {
        heading: "4. If a customer contacted you using our Service",
        body: [
          "The business that emailed you is responsible for how your details were obtained and used. Every email sent through our Service includes an unsubscribe link, and opting out stops further emails from that business. You can also ask that business, or us, to help with access or erasure requests; we will pass requests to the customer and assist them.",
        ],
      },
      {
        heading: "5. Sharing",
        body: [
          "We use carefully selected subprocessors to run the Service (see our Subprocessors page). We do not sell personal data. We disclose data to authorities only where legally required.",
        ],
      },
      {
        heading: "6. International transfers",
        body: [
          "Where data is transferred outside the UK or EEA we rely on adequacy decisions or standard contractual clauses with appropriate safeguards.",
        ],
      },
      {
        heading: "7. Retention",
        body: [
          "We keep account data while your account is open and for a limited period afterwards for legal and accounting purposes. Customers set retention rules for their own workspace data.",
        ],
      },
      {
        heading: "8. Your rights",
        body: [
          `You can access, correct, export or delete your personal data, object to or restrict processing, and withdraw consent at any time. Contact ${SITE.privacyEmail}. You may also complain to your data protection authority.`,
        ],
      },
      {
        heading: "9. Security",
        body: [
          "We protect data with encryption in transit, encryption of stored credentials, database-level tenant isolation, two-factor authentication, access logging and regular security testing.",
        ],
      },
    ],
  },
  {
    slug: "dpa",
    title: "Data Processing Agreement",
    summary: "The terms under which we process personal data on our customers' behalf (GDPR Article 28).",
    updated: UPDATED,
    sections: [
      {
        heading: "1. Scope and roles",
        body: [
          `This agreement forms part of the Terms of Service. The customer is the controller and ${E} is the processor of personal data the customer submits to the Service ("Customer Data").`,
        ],
      },
      {
        heading: "2. Instructions",
        body: [
          "We process Customer Data only on the customer's documented instructions, which are the Terms, this agreement and the customer's use of the Service's features, unless the law requires otherwise.",
        ],
      },
      {
        heading: "3. Details of processing",
        body: [
          [
            "Subject matter: providing a lead management and email outreach service.",
            "Data subjects: the customer's prospects and contacts, and the customer's users.",
            "Categories of data: names, job titles, business contact details, company information, email content and replies.",
            "Duration: the term of the agreement plus the deletion period below.",
          ],
        ],
      },
      {
        heading: "4. Confidentiality and security",
        body: [
          "Personnel with access to Customer Data are bound by confidentiality. We maintain appropriate technical and organisational measures, including encryption, access control, tenant isolation, logging, backups and incident response.",
        ],
      },
      {
        heading: "5. Subprocessors",
        body: [
          "The customer authorises the subprocessors listed on our Subprocessors page. We give at least 30 days' notice of new platform subprocessors, during which the customer may object. We impose equivalent data protection obligations on each subprocessor.",
        ],
      },
      {
        heading: "6. Assistance",
        body: [
          "We help the customer respond to data subject requests (including through the in-app export and erasure tools), and with security, breach notification, impact assessments and consultations, taking into account the nature of the processing.",
        ],
      },
      {
        heading: "7. Personal data breaches",
        body: ["We notify the customer without undue delay, and in any case within 48 hours, after becoming aware of a breach affecting Customer Data."],
      },
      {
        heading: "8. Deletion and return",
        body: [
          "The customer can export Customer Data at any time. After the account closes we delete Customer Data within 30 days, except where retention is legally required.",
        ],
      },
      {
        heading: "9. Audits",
        body: [
          "We make available the information needed to demonstrate compliance and allow for audits on reasonable notice, normally satisfied by our security documentation and third-party reports where available.",
        ],
      },
    ],
  },
  {
    slug: "acceptable-use",
    title: "Acceptable Use Policy",
    summary: "What you may and may not do with the Service.",
    updated: UPDATED,
    sections: [
      {
        heading: "You must",
        body: [
          [
            "Only contact people where you have a lawful basis, and keep a record of it.",
            "Identify yourself honestly and include a working unsubscribe link and your postal address.",
            "Honour opt-outs immediately and never re-add suppressed contacts.",
            "Send relevant, individual business messages rather than bulk promotions.",
          ],
        ],
      },
      {
        heading: "You must not",
        body: [
          [
            "Upload or contact purchased, rented or scraped lists of personal email addresses.",
            "Send spam, phishing, malware or deceptive content, or spoof headers and sender identities.",
            "Target consumers in jurisdictions where unsolicited electronic marketing to individuals is prohibited.",
            "Use the Service to harass anyone or to process special-category data.",
            "Attempt to break, overload or get around the Service's security, rate limits or sending limits.",
          ],
        ],
      },
      {
        heading: "Enforcement",
        body: [
          "We monitor bounce and complaint rates. We may pause sending, suspend accounts or end the agreement where this policy is breached or the Service's reputation is at risk. Report abuse to " +
            SITE.contactEmail +
            ".",
        ],
      },
    ],
  },
  {
    slug: "cookies",
    title: "Cookie Policy",
    summary: "The cookies and similar technologies we use, and your choices.",
    updated: UPDATED,
    sections: [
      {
        heading: "Essential",
        body: [
          [
            "Session: keeps you signed in (an httpOnly refresh cookie and a session hint).",
            "Security: single sign-on state and bot protection on sign-up and sign-in forms.",
            "Preferences: your chosen workspace and cookie choice, stored in your browser.",
          ],
          "These are needed for the Service to work and don't require consent.",
        ],
      },
      {
        heading: "Analytics (optional)",
        body: [
          "With your consent we use product analytics to understand which pages and features help people. You can change your choice at any time by clearing the cookie preference in your browser; the banner will ask again.",
        ],
      },
      {
        heading: "Error monitoring",
        body: ["If the app crashes we record technical details about the error to fix it. This does not track you across sites."],
      },
    ],
  },
];

export function legalDocument(slug: string): LegalDocument | undefined {
  return LEGAL_DOCUMENTS.find((doc) => doc.slug === slug);
}

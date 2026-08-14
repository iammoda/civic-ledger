import type { BillDetail, PoliticianDetail } from "@/lib/api";

/**
 * schema.org structured data for the two page types search engines
 * understand best here: Legislation (bills) and Person (representatives).
 * Rendered as <script type="application/ld+json"> by the pages.
 */

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export function billLegislationJsonLd(bill: BillDetail): Record<string, unknown> {
  const status =
    bill.is_law ? "https://schema.org/Commenced" : bill.outcome === "in_progress" ? "https://schema.org/Pending" : undefined;
  return {
    "@context": "https://schema.org",
    "@type": "Legislation",
    name: bill.short_title_en ?? bill.title_en,
    legislationIdentifier: bill.number,
    legislationType: billLegislationType(bill.bill_type),
    description: bill.one_sentence ?? bill.status_en ?? undefined,
    legislationDate: bill.introduced_on ?? undefined,
    legislationLegalForce: status,
    legislationPassedBy: bill.chamber === "senate" ? "Senate of Canada" : "House of Commons of Canada",
    url: `${SITE_URL}/bills/${bill.session}/${bill.number}`,
    ...(bill.sponsor_name
      ? {
          sponsor: {
            "@type": "Person",
            name: bill.sponsor_name,
            ...(bill.sponsor_slug ? { url: `${SITE_URL}/politicians/${bill.sponsor_slug}` } : {})
          }
        }
      : {})
  };
}

function billLegislationType(billType: string): string {
  return billType === "private_member" ? "Private Member's Bill" : "Government Bill";
}

export function personJsonLd(politician: PoliticianDetail): Record<string, unknown> {
  const membership = politician.current_membership;
  const level = politician.level ?? "federal";
  const jobTitle =
    level === "federal"
      ? "Member of Parliament"
      : level === "provincial"
        ? "Member of Provincial Parliament"
        : "Municipal representative";
  return {
    "@context": "https://schema.org",
    "@type": "Person",
    name: politician.full_name,
    jobTitle,
    ...(membership?.party?.name ? { memberOf: { "@type": "Organization", name: membership.party.name } } : {}),
    ...(membership?.riding_name ? { workLocation: { "@type": "Place", name: membership.riding_name } } : {}),
    ...(politician.image_url ? { image: politician.image_url } : {}),
    ...(politician.website_url ? { sameAs: [politician.website_url] } : {}),
    url: `${SITE_URL}/politicians/${politician.slug}`
  };
}

export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />;
}

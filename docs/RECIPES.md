# Συνταγές για NetLogik API Intelligence

Οι παρακάτω συνδυασμοί είναι προτάσεις υλοποίησης από τον κατάλογο. Δεν αποτελούν ήδη εγκατεστημένες εφαρμογές ή δοκιμές εκτέλεσης των APIs. Οι δημόσιες σελίδες τεκμηρίωσης ελέγχθηκαν σε συγκεκριμένη χρονική στιγμή· οι χρονοσημάνσεις και τα αποτελέσματα βρίσκονται στο [αρχείο ελέγχων](../netlogik/evidence/live-validation.json).

## NetLogik Knowledge Ingest

Μετατροπή εταιρικών ιστοσελίδων και εγγράφων σε καθαρό υλικό για το υπάρχον RAG.

**Υποψήφιες διασυνδέσεις:**

- [website-content-crawler](https://apify.com/apify/website-content-crawler)
- [ai-document-extract-document](https://apyhub.com/utility/ai-document-extract-document)

**Παραδοτέο:** Source URL, retrieved timestamp, content hash, extracted text, changed-page report, RAG ingestion job.

## SPK Travel Intelligence

Παρακολούθηση τιμών καταλυμάτων και συγκέντρωση αξιολογήσεων για τουριστικά έργα.

**Υποψήφιες διασυνδέσεις:**

- [booking-scraper](https://apify.com/voyager/booking-scraper)
- [tripadvisor-scraper](https://apify.com/nexgendata/tripadvisor-scraper)
- [tripadvisor-reviews](https://apify.com/agents/tripadvisor-reviews)

**Παραδοτέο:** Hotel comparison dashboard, normalized date/currency data, review sentiment and evidence links.

## NetLogik Local Business Research

Έρευνα επιχειρήσεων ανά περιοχή, εμπλουτισμός CRM και έλεγχος ιστοσελίδων.

**Υποψήφιες διασυνδέσεις:**

- [crawler-google-places](https://apify.com/compass/crawler-google-places)
- [website-content-crawler](https://apify.com/apify/website-content-crawler)

**Παραδοτέο:** Deduplicated company records with provenance and web audit; outreach is a separate user-authorized action.

## SEO and AI Visibility Monitor

Έλεγχος οργανικών αποτελεσμάτων, ανταγωνιστών και εμφανίσεων σε απαντήσεις AI.

**Υποψήφιες διασυνδέσεις:**

- [google-search-scraper](https://apify.com/apify/google-search-scraper)
- [ai-brand-monitoring](https://apify.com/inovaflow/ai-brand-monitoring)

**Παραδοτέο:** Keyword/location snapshots, ranking changes, citations and client reports.

## Greek Property Research

Συγκέντρωση αγγελιών ακινήτων και παρακολούθηση τιμών ανά περιοχή στην Ελλάδα.

**Υποψήφιες διασυνδέσεις:**

- [spitogatos-scraper](https://apify.com/swerve/spitogatos-scraper)
- [xe-gr-real-estate-scraper-greece-property-data](https://apify.com/logiover/xe-gr-real-estate-scraper-greece-property-data)

**Παραδοτέο:** Property comparison with date, location, asking price, price per square metre, duplicate detection, source URLs.

## Document Processing Desk

Εξαγωγή στοιχείων παραστατικών, μετατροπές αρχείων και υποστήριξη διοικητικών εργασιών.

**Υποψήφιες διασυνδέσεις:**

- [ai-document-extract-invoice](https://apyhub.com/utility/ai-document-extract-invoice)
- [ai-document-extract-receipt](https://apyhub.com/utility/ai-document-extract-receipt)

**Παραδοτέο:** Structured draft records and confidence checks for human review; provider-specific API schemas required.

## Commerce Price Watch

Παρακολούθηση τιμών προϊόντων και συγκρίσεις για ηλεκτρονικά καταστήματα.

**Υποψήφιες διασυνδέσεις:**

- [amazon-crawler](https://apify.com/junglee/amazon-crawler)

**Παραδοτέο:** Timestamped product/variant identifiers, currency, price, availability and changes dashboard.

## Local Review Monitor

Συγκέντρωση κριτικών και θεμάτων εξυπηρέτησης για τοπικές επιχειρήσεις.

**Υποψήφιες διασυνδέσεις:**

- [google-maps-reviews-scraper](https://www.coreclaw.com/coreclaw/google-maps-reviews-scraper)

**Παραδοτέο:** Review timeline, recurring complaints, response drafts for human approval.

## Επόμενο βήμα για οποιαδήποτε συνταγή

Πριν από την πραγματική σύνδεση χρειάζονται η τρέχουσα τεκμηρίωση του επιλεγμένου παρόχου, το input/output schema, διαθέσιμος λογαριασμός όπου απαιτείται, καθορισμένο δείγμα δοκιμής και προϋπολογισμός. Τα αρχικά links του καταλόγου είναι σελίδες προϊόντων ή τεκμηρίωσης και δεν θεωρούνται αυτόματα callable endpoints.

Οι δομημένες εγγραφές, οι δημόσιες πηγές, οι πιθανές ανακατευθύνσεις και τα βήματα προετοιμασίας υπάρχουν στο [recipes.json](../netlogik/recipes.json).

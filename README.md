# NetLogik API Intelligence

Η προσωπική βιβλιοθήκη API του **Giannis / NetLogik**: ένας καθαρισμένος, αναζητήσιμος κατάλογος για σχεδιασμό εφαρμογών, αυτοματισμούς, MCP και RAG, βασισμένος στο fork του [API Mega List](https://github.com/giannisasini/API-mega-list).

**11.981 μοναδικές εγγραφές · 23 βασικές κατηγορίες · αναζήτηση εκτός σύνδεσης · Python χωρίς εξωτερικά πακέτα.**

| Περιεχόμενο | Πραγματική καταμέτρηση |
|---|---:|
| APIs στους βασικούς πίνακες | 11.660 |
| Sponsored ApyHub / CoreClaw | 200 / 118 |
| Πρόσθετες δοκιμαστικές εγγραφές του raw αρχείου, με `raw_only` | 3 |
| Εμφανίσεις που ενοποιήθηκαν με διατήρηση προέλευσης | 79.313 |
| Περιγραφές που εμπλουτίστηκαν από την αρχική πλήρη καταχώριση | 7.228 |

## Ξεκίνα σε ένα λεπτό

Απαιτείται **Python 3.10+**. Από τον φάκελο του repository:

```bash
python3 netlogik/catalog.py search "google maps" --limit 5
python3 netlogik/catalog.py search "invoice" --provider apyhub --flag sponsored
python3 netlogik/catalog.py search "ακίνητα" --category real-estate --limit 5
python3 netlogik/catalog.py search --provider coreclaw --limit 5
python3 netlogik/catalog.py stats
```

Στην πρώτη εκτέλεση δημιουργείται αυτόματα η τοπική SQLite από το συμπιεσμένο αρχείο που περιλαμβάνεται εδώ. Χρειάζονται περίπου **175 MB** επιπλέον δίσκου. Η διαδικασία λειτουργεί χωρίς δίκτυο, λογαριασμό ή API key και δεν καλεί εξωτερικά APIs. Τα αποτελέσματα είναι JSON και περιλαμβάνουν τα σταθερά IDs, τις αρχικές πηγές και τις ενδείξεις επαλήθευσης.

Για πλήρη καταχώριση χρησιμοποίησε το `id` που επιστρέφει η αναζήτηση ή το canonical URL:

```bash
python3 netlogik/catalog.py get "https://apify.com/apify/ai-code-sandbox"
python3 netlogik/catalog.py search "invoice" --like --limit 3
python3 -m unittest discover -s netlogik/tests -v
```

Η κανονική αναζήτηση χρησιμοποιεί SQLite FTS5. Το `--like` ενεργοποιεί την εναλλακτική αναζήτηση, η οποία αγνοεί κεφαλαία και τόνους. Τα φίλτρα `--provider`, `--category`, `--flag` συνδυάζονται· τα `--limit` και `--offset` επιτρέπουν σελιδοποίηση. Οι ελληνικοί όροι καλύπτουν τις μεταφρασμένες κατηγορίες· οι περιγραφές διατηρούν τη γλώσσα της πηγής.

## Τι μπορώ να χτίσω πάνω του

- **Βοηθό επιλογής API:** περιγράφεις μια ανάγκη και λαμβάνεις υποψήφιες διασυνδέσεις, πηγές και σημεία που χρειάζονται δοκιμή.
- **Εργαλείο έρευνας αγοράς:** συνδυασμό αναζήτησης προϊόντων, τιμών, κριτικών και εταιρικών δεδομένων με δικό σου dashboard.
- **Βοηθό ταξιδιών και ακινήτων:** ανακάλυψη πιθανών παρόχων για πτήσεις, ξενοδοχεία, καταλύματα και καταχωρίσεις ακινήτων.
- **Ροές εγγράφων και περιεχομένου:** επιλογές για τιμολόγια, μετατροπές αρχείων, εξαγωγή δεδομένων, μεταγραφές και SEO.
- **MCP και RAG discovery:** ο κατάλογος προσφέρει σταθερά IDs και ακριβή προέλευση για εργαλεία αναζήτησης και ανάκτησης γνώσης.

Η επιλογή ενός API είναι το πρώτο βήμα. Η πραγματική σύνδεση χρειάζεται ξεχωριστό έλεγχο τεκμηρίωσης, input schema, λογαριασμού και κόστους του παρόχου.

## Τι υπάρχει μέσα

| Αρχείο | Χρήση |
|---|---|
| [`netlogik/catalog.py`](netlogik/catalog.py) | Αναζήτηση, ανάκτηση και στατιστικά από την τοπική SQLite |
| [`netlogik/build_catalog.py`](netlogik/build_catalog.py) | Αναπαραγωγή του καταλόγου από επαληθευμένο snapshot |
| [`netlogik/dist/catalog.json.gz`](netlogik/dist/catalog.json.gz) | Ο ίδιος πλήρης κατάλογος συμπιεσμένος, χωρίς απώλεια πεδίων |
| [`netlogik/recipes.json`](netlogik/recipes.json) | Οκτώ συγκεκριμένες συνταγές εφαρμογών με υποψήφια APIs και απαιτήσεις σύνδεσης |
| [`docs/RECIPES.md`](docs/RECIPES.md) | Ελληνικός οδηγός των προτεινόμενων συνδυασμών |
| [`docs/MCP.md`](docs/MCP.md) | Τα τρία εργαλεία MCP, εγκατάσταση και σημασιολογική ανακάλυψη στο RAG |
| [`netlogik/mcp/api-catalog.mjs`](netlogik/mcp/api-catalog.mjs) | Το ελεγμένο module αναζήτησης για τον NetLogik MCP host |
| [`netlogik/evidence/live-validation.json`](netlogik/evidence/live-validation.json) | Χρονοσημασμένοι έλεγχοι προσβασιμότητας δημόσιας τεκμηρίωσης |
| [`netlogik/dist/stats.json`](netlogik/dist/stats.json) | Μετρημένα μεγέθη, κατηγορίες, flags και διαφορές από τα upstream badges |
| [`netlogik/dist/source-coverage.json`](netlogik/dist/source-coverage.json) | Κάλυψη όλων των πηγών και SHA-256 ανά αρχείο |
| [`netlogik/dist/artifact-manifest.json`](netlogik/dist/artifact-manifest.json) | Έλεγχος ακεραιότητας των παραγόμενων αρχείων |
| [`netlogik/source-snapshot.json`](netlogik/source-snapshot.json) | Commit και hashes για την αναπαραγωγή της αρχικής πηγής |
| [`UPSTREAM_README.md`](UPSTREAM_README.md) | Το αρχικό README, αυτούσιο για attribution και provenance |

Η ενοποίηση γίνεται με βάση το URL και όχι το όνομα. Αφαιρούνται μόνο τα αναγνωρισμένα tracking parameters `fpr` και `utm_*`· λειτουργικές παράμετροι και άγνωστα `ref` διατηρούνται. Κάθε εγγραφή κρατά τις αρχικές διευθύνσεις, όλες τις εμφανίσεις της, το αρχείο, τη γραμμή και την κατηγορία της πηγής. Για Apify διατηρούνται επίσης `owner` και `slug`.

Όλες οι περιγραφές αποτελούν **μη επαληθευμένους ισχυρισμούς της πηγής**. Το `sponsored` διακρίνει τις χορηγούμενες συλλογές, το `raw_only` τις τρεις πρόσθετες δοκιμαστικές καταχωρίσεις και το `description_truncated` τις 172 περιγραφές που παραμένουν κομμένες. Τα διαφημιζόμενα upstream μεγέθη 11.860 / 24 διορθώνονται εδώ σε 11.660 / 23 βάσει των πραγματικών πινάκων.

## Αναπαραγωγή του build

```bash
python3 netlogik/build_catalog.py
```

Το build επαληθεύει τα hashes των διατηρημένων πηγών και χρησιμοποιεί το αρχικό `UPSTREAM_README.md` στη θέση του upstream `README.md`. Δημιουργεί ξανά JSON, gzip, SQLite, στατιστικά και manifest. Το `netlogik/dist/catalog.runtime.json` που παράγεται είναι πλήρες JSON μιας γραμμής για MCP ή άλλο τοπικό εργαλείο. Το gzip έχει σταθερό timestamp και η ημερομηνία του καταλόγου προέρχεται από το commit, ώστε το ίδιο snapshot να παράγει τα ίδια αποτελέσματα. Τα μη συμπιεσμένα JSON και η SQLite εξαιρούνται από το Git· το repository περιλαμβάνει το πλήρες gzip περίπου 3,5 MB.

Εναλλακτικά, μπορείς να περάσεις καθαρό checkout του αρχικού commit:

```bash
python3 netlogik/build_catalog.py --source /path/to/pinned-upstream-checkout
```

Πηγή: [cporter202/API-mega-list](https://github.com/cporter202/API-mega-list), commit [`be78c4e79b5f31f6969ebdb94396942d64c6cf95`](https://github.com/cporter202/API-mega-list/tree/be78c4e79b5f31f6969ebdb94396942d64c6cf95). Διατηρούνται οι αρχικοί δημιουργοί, περιγραφές και πηγές. Το fork και το επίπεδο οργάνωσης NetLogik δεν μεταβιβάζουν κυριότητα στα APIs ή στις υπηρεσίες τρίτων. Δεν προστίθεται γενική άδεια που να καλύπτει περιεχόμενο τρίτων.

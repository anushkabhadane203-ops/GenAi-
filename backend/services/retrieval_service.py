import os
import csv
import re
import logging
import math
from collections import Counter
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.models import KnowledgeEntry

logger = logging.getLogger("retrieval_service")

# Cross-lingual expansion map for education & Maharashtra schemes
MULTILINGUAL_EXPANSIONS = {
    # Scholarship
    "scholarship": ["शिष्यवृत्ती", "छात्रवृत्ति", "શિષ્યવૃત્તિ", "கல்வி உதவித்தொகை", "స్కాలర్‌షిప్", "বৃত্তি", "scholarship", "freestudentship"],
    "शिष्यवृत्ती": ["scholarship", "छात्रवृत्ति", "शिष्यवृत्ती", "mahadbt"],
    "छात्रवृत्ति": ["scholarship", "शिष्यवृत्ती", "छात्रवृत्ति", "mahadbt"],
    "स्कॉलरशिप": ["scholarship", "शिष्यवृत्ती", "छात्रवृत्ति"],
    # Hostel
    "hostel": ["वसतिगृह", "छात्रावास", "हॉस्टल", "છાત્રાલય", "swadhar", "ज्ञानज्योती सावित्रीबाई फुले"],
    "वसतिगृह": ["hostel", "छात्रावास", "हॉस्टल", "swadhar"],
    "हॉस्टल": ["hostel", "वसतिगृह", "छात्रावास"],
    "छात्रावास": ["hostel", "वसतिगृह"],
    # Eligibility & Criteria
    "eligibility": ["पात्रता", "योग्यता", "criteria", "rules", "शर्ती"],
    "पात्रता": ["eligibility", "criteria", "पात्रता", "conditions"],
    "योग्यता": ["eligibility", "पात्रता"],
    # Fees & Reimbursement
    "fees": ["शुल्क", "फीस", "फी", "tuition", "exam fee", "fee reimbursement"],
    "शुल्क": ["fees", "फीस", "fee reimbursement", "tuition"],
    "फीस": ["fees", "शुल्क", "फी"],
    # Income limit
    "income": ["उत्पन्न", "आय", "आवक", "income limit", "creamy layer", "8 lakh", "उत्पन्नाची अट"],
    "उत्पन्न": ["income", "income limit", "उत्पन्न", "non creamy layer"],
    "आय": ["income", "उत्पन्न", "आय प्रमाण"],
    # Foreign / abroad studies
    "foreign": ["विदेश", "परदेश", "abroad", "foreign scholarship", "75 seats"],
    "विदेश": ["foreign", "परदेश", "abroad", "विदेश शिष्यवृत्ती"],
    "परदेश": ["foreign", "विदेश", "abroad", "परदेशी शिक्षण"],
    # Seats and Reservation
    "seats": ["जागा", "सीट", "आरक्षण", "capacity", "quota", "intake"],
    "जागा": ["seats", "capacity", "जागा", "intake"],
    "सीट": ["seats", "जागा", "capacity"],
    "आरक्षण": ["reservation", "quota", "आरक्षण", "obc quota"],
    "reservation": ["आरक्षण", "quota", "seats", "जागा"],
    # Documents
    "documents": ["कागदपत्रे", "दस्तावेज़", "certificate", "caste certificate", "income certificate"],
    "कागदपत्रे": ["documents", "certificate", "कागदपत्रे"],
    "दस्तावेज़": ["documents", "कागदपत्रे"],
    "kagaz": ["documents", "कागदपत्रे", "दस्तावेज़", "certificate"],
    "dastavez": ["documents", "कागदपत्रे", "दस्तावेज़"],
    # Hinglish application & procedural terms
    "kaise": ["application", "portal", "mahadbt", "अर्ज", "आवेदन", "steps"],
    "karein": ["application", "portal", "mahadbt", "अर्ज", "आवेदन"],
    "apply": ["application", "portal", "mahadbt", "अर्ज", "आवेदन", "फॉर्म"],
    "bharna": ["application", "portal", "mahadbt", "फॉर्म"],
    "kitna": ["allowance", "fees", "amount", "रक्कम", "भत्ता", "stipend"],
    "paisa": ["allowance", "fees", "amount", "रक्कम", "भत्ता", "stipend"],
    # Gujarati key concepts
    "શિષ્યવૃત્તિ": ["scholarship", "शिष्यवृत्ती", "छात्रवृत्ति", "mahadbt"],
    "સ્કોલરશિપ": ["scholarship", "शिष्यवृत्ती", "छात्रवृत्ति", "mahadbt"],
    "છાત્રાલય": ["hostel", "वसतिगृह", "swadhar"],
    "હોસ્ટેલ": ["hostel", "वसतिगृह", "swadhar"],
    "લાયકાત": ["eligibility", "criteria", "पात्रता"],
    "ફી": ["fees", "tuition", "शुल्क", "fee reimbursement"],
    "આવક": ["income", "creamy layer", "8 lakh", "उत्पन्न"],
    "પ્રવેશ": ["admission", "process", "eligibility", "प्रवेश"],
    "કાગળો": ["documents", "कागदपत्रे", "certificate"],
    "અરજી": ["application", "apply", "mahadbt", "अर्ज"],
    # Tamil, Telugu, Bengali concepts
    "கல்வி": ["education", "scholarship", "शिक्षण"],
    "கட்டணம்": ["fees", "tuition", "शुल्क"],
    "தகுதி": ["eligibility", "criteria", "पात्रता"],
    "విద్యా": ["education", "scholarship", "शिक्षण"],
    "ఫీజు": ["fees", "tuition", "शुल्क"],
    "అర్హత": ["eligibility", "criteria", "पात्रता"],
    "শিক্ষা": ["education", "scholarship", "शिक्षण"],
    "ফি": ["fees", "tuition", "शुल्क"],
    "যোগ্যতা": ["eligibility", "criteria", "पात्रता"],
    # Gujlish & Hinglish admission & course terms
    "admission": ["प्रवेश", "admission", "eligibility", "criteria", "college", "course"],
    "process": ["application", "steps", "procedure", "अर्ज", "आवेदन", "mahadbt"],
    "colleges": ["college", "engineering", "medical", "polytechnic", "महाविद्यालय"],
    "allowance": ["maintenance allowance", "भत्ता", "stipend", "रक्कम", "निर्वाह"],
    "girls": ["मुली", "कन्‍या", "girls", "savitribai", "phule", "women"],
    "ladkiyon": ["girls", "मुली", "कन्‍या", "savitribai"],
    "mulina": ["girls", "मुली", "कन्‍या", "savitribai"],
}


def _ngram_counts(text: str, ngram_range: tuple[int, int]) -> Counter:
    tokens = re.findall(r"(?u)\b\w+\b", text.lower())
    return Counter(
        " ".join(tokens[index:index + size])
        for size in range(ngram_range[0], ngram_range[1] + 1)
        for index in range(len(tokens) - size + 1)
    )


def _tfidf_vector(counts: Counter, document_count: int, document_frequency: Counter) -> Dict[str, float]:
    vector = {
        term: (1 + math.log(count)) * (math.log((1 + document_count) / (1 + document_frequency[term])) + 1)
        for term, count in counts.items()
    }
    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
    if norm:
        return {term: weight / norm for term, weight in vector.items()}
    return vector


def tfidf_cosine_similarity(left: str, right: str, ngram_range: tuple[int, int] = (1, 2)) -> float:
    """Calculate sublinear TF-IDF cosine similarity without native ML dependencies."""
    counts = [_ngram_counts(text, ngram_range) for text in (left, right)]
    document_frequency = Counter(term for terms in counts for term in terms)
    vectors = [_tfidf_vector(terms, len(counts), document_frequency) for terms in counts]
    return sum(weight * vectors[1].get(term, 0.0) for term, weight in vectors[0].items())


class HybridKnowledgeRetriever:
    """Pure-Python TF-IDF and keyword retriever with multilingual expansion."""

    def __init__(self):
        self.entries: List[Dict[str, Any]] = []
        self.tfidf_matrix: List[Dict[str, float]] = []
        self.document_frequency: Counter = Counter()
        self.is_ready = False

    def _prepare_corpus(self, entries: List[Dict[str, Any]]) -> List[str]:
        corpus = []
        for e in entries:
            title = (e.get("title") or "") * 2
            keywords = (e.get("keywords") or "") * 2
            multilingual = (e.get("multilingual_terms") or "") * 2
            query_variants = (e.get("query_variants") or "") * 2
            cat = e.get("category") or ""
            rec_type = e.get("record_type") or ""
            retrieval = e.get("retrieval_text") or ""
            content = e.get("content") or ""
            text_parts = [title, keywords, multilingual, query_variants, cat, rec_type, retrieval, content]
            corpus.append(" ".join(filter(None, text_parts)))
        return corpus

    def index_entries(self, entries: List[Dict[str, Any]]):
        """Build or refresh in-memory index from knowledge entries."""
        if not entries:
            self.entries = []
            self.tfidf_matrix = []
            self.document_frequency = Counter()
            self.is_ready = False
            return

        self.entries = entries
        corpus = self._prepare_corpus(entries)
        term_counts = [_ngram_counts(text, (1, 3)) for text in corpus]
        self.document_frequency = Counter(
            term for terms in term_counts for term in terms
        )
        self.tfidf_matrix = [
            _tfidf_vector(terms, len(term_counts), self.document_frequency)
            for terms in term_counts
        ]
        self.is_ready = True
        logger.info(f"Indexed {len(entries)} knowledge entries successfully.")

    def _expand_query(self, query: str) -> str:
        """Expand search query with synonyms and cross-lingual terms."""
        q_lower = query.lower()
        expanded_terms = set(re.findall(r"\w+", q_lower))

        for word in list(expanded_terms):
            if word in MULTILINGUAL_EXPANSIONS:
                expanded_terms.update(MULTILINGUAL_EXPANSIONS[word])

        return query + " " + " ".join(expanded_terms)

    def search(
        self,
        query: str,
        top_k: int = 5,
        record_type: Optional[str] = None,
        min_score: float = 0.05
    ) -> List[Dict[str, Any]]:
        """Retrieve most relevant knowledge entries for query."""
        if not query.strip():
            return []

        if not self.is_ready or not self.entries:
            try:
                from backend.database import SessionLocal
                _db = SessionLocal()
                try:
                    reload_retriever_from_db(_db)
                finally:
                    _db.close()
            except Exception as e:
                logger.warning(f"Auto-reload retriever failed: {e}")

        if not self.is_ready or not self.entries:
            return []

        expanded_query = self._expand_query(query)

        query_counts = _ngram_counts(expanded_query, (1, 3))
        query_vector = _tfidf_vector(
            query_counts, len(self.entries), self.document_frequency
        )
        sim_scores = [
            sum(weight * document.get(term, 0.0) for term, weight in query_vector.items())
            for document in self.tfidf_matrix
        ]

        scored_entries = []
        q_tokens = set(re.findall(r"\w+", query.lower()))

        for idx, score in enumerate(sim_scores):
            entry = self.entries[idx]

            # Optional filter by record_type
            if record_type and entry.get("record_type") != record_type:
                continue

            final_score = float(score)

            # Boost exact title and keywords overlap
            title_lower = entry.get("title", "").lower()
            if any(t in title_lower for t in q_tokens if len(t) > 2):
                final_score += 0.15

            # Scheme priority for scheme-specific eligibility questions
            if entry.get("record_type") == "scheme" and any(k in query.lower() for k in ["scheme", "scholarship", "eligibility", "योजना", "शिष्यवृत्ती"]):
                final_score += 0.08

            if final_score >= min_score:
                entry_copy = dict(entry)
                entry_copy["relevance_score"] = round(final_score, 4)
                scored_entries.append((final_score, entry_copy))

        scored_entries.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_entries[:top_k]]


# Global singleton retriever instance
retriever = HybridKnowledgeRetriever()


def reload_retriever_from_db(db: Session):
    """Load all active knowledge entries from SQLite and refresh retriever index."""
    entries_db = db.query(KnowledgeEntry).filter(KnowledgeEntry.indexing_status == "indexed").all()
    entries_data = []
    for e in entries_db:
        entries_data.append({
            "id": e.id,
            "knowledge_id": e.knowledge_id,
            "title": e.title,
            "content": e.content,
            "retrieval_text": e.retrieval_text or e.content,
            "record_type": e.record_type,
            "category": e.category,
            "scheme_id": e.scheme_id,
            "official_source": e.official_source,
            "source_quality": e.source_quality,
            "data_status": e.data_status,
            "seat_capacity": e.seat_capacity,
            "validity_notes": e.validity_notes,
            "response_disclaimer": e.response_disclaimer,
            "keywords": e.keywords,
            "multilingual_terms": e.multilingual_terms,
            "query_variants": e.query_variants,
            "source_type": e.source_type,
            "source_filename": e.source_filename,
        })
    retriever.index_entries(entries_data)
    logger.info(f"Retriever reloaded with {len(entries_data)} entries from database.")


def seed_knowledge_from_csv(db: Session, force: bool = False):
    """Seed knowledge base from the project dataset CSV files if empty or forced."""
    count = db.query(KnowledgeEntry).count()
    if count > 0 and not force:
        logger.info(f"Knowledge database already contains {count} entries. Skipping seeding.")
        reload_retriever_from_db(db)
        return

    csv_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw", "maharashtra_obc_chatbot_knowledgebase_expanded.csv"),
        os.path.join("data", "raw", "maharashtra_obc_chatbot_knowledgebase_expanded.csv"),
        "maharashtra_obc_chatbot_knowledgebase_expanded.csv"
    ]
    csv_path = next((p for p in csv_candidates if os.path.exists(p)), None)
    if not csv_path:
        logger.warning("Knowledgebase CSV not found in data/raw or current directory.")
        return

    logger.info(f"Seeding knowledge base from {csv_path}...")
    new_entries = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cleaned = {k.lstrip("\ufeff"): v for k, v in row.items()}
            knowledge_id = cleaned.get("knowledge_id") or cleaned.get("record_id")
            title = cleaned.get("title") or cleaned.get("scheme_name") or "Maharashtra OBC Scheme"
            detailed = cleaned.get("answer_detailed") or cleaned.get("answer_short") or cleaned.get("benefit_summary") or ""
            retrieval = cleaned.get("retrieval_text") or f"{title}. {detailed}"

            entry = KnowledgeEntry(
                knowledge_id=knowledge_id,
                title=title,
                content=detailed or retrieval,
                retrieval_text=retrieval,
                record_type=cleaned.get("record_type") or "scheme",
                category=cleaned.get("category") or "education_scheme",
                scheme_id=cleaned.get("scheme_id") or knowledge_id,
                official_source=cleaned.get("official_scheme_source_normalized") or cleaned.get("official_scheme_source"),
                source_quality=cleaned.get("source_quality") or "official",
                data_status=cleaned.get("data_status_normalized") or cleaned.get("data_status") or "verified",
                seat_capacity=cleaned.get("seat_capacity"),
                validity_notes=cleaned.get("validity_notes"),
                response_disclaimer=cleaned.get("response_disclaimer"),
                keywords=cleaned.get("keywords"),
                multilingual_terms=cleaned.get("multilingual_terms"),
                query_variants=cleaned.get("query_variants"),
                source_type="dataset",
                source_filename=os.path.basename(csv_path),
                indexing_status="indexed"
            )
            new_entries.append(entry)

    if new_entries:
        db.bulk_save_objects(new_entries)
        db.commit()
        logger.info(f"Successfully seeded {len(new_entries)} knowledge entries into SQLite.")

    reload_retriever_from_db(db)

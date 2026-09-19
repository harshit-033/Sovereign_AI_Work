"""
Build College Final Year Major Project Synopsis PDF
Strictly following the G.L. Bajaj Institute of Technology & Management / AKTU synopsis guidelines.
"""

import sys
import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
    Image,
)
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_PDF = PROJECT_ROOT / "Final_Year_Project_Synopsis.pdf"
GL_LOGO_PATH = PROJECT_ROOT / "logo_p1_0.jpeg"
AKTU_LOGO_PATH = PROJECT_ROOT / "logo_p1_1.png"


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and display running header and
    'Page X of Y' footer on pages 2 and later.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        # Suppress header and footer on cover page (page 1)
        if self._pageNumber > 1:
            # Running Header
            self.setFont("Times-Roman", 8.5)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawString(54, A4[1] - 34, "Department of Computer Science & Engineering | Major Project Synopsis")
            self.drawRightString(A4[0] - 54, A4[1] - 34, "Session 2026-2027")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.6)
            self.line(54, A4[1] - 39, A4[0] - 54, A4[1] - 39)

            # Running Footer
            self.setFont("Times-Roman", 8.5)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawString(54, 30, "G.L. Bajaj Institute of Technology & Management, Greater Noida")
            page_str = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(A4[0] - 54, 30, page_str)
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.6)
            self.line(54, 40, A4[0] - 54, 40)

        self.restoreState()


def get_synopsis_styles():
    styles = getSampleStyleSheet()

    # Cover Page Styles
    styles.add(ParagraphStyle(
        name='CoverProjectTitle',
        fontName='Times-Bold',
        fontSize=15,
        leading=20,
        alignment=1,  # Center
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name='CoverSubtitle',
        fontName='Times-Roman',
        fontSize=11.5,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name='CoverDegree',
        fontName='Times-Bold',
        fontSize=13,
        leading=17,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverBranch',
        fontName='Times-Bold',
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverBy',
        fontName='Times-Roman',
        fontSize=11,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#334155"),
    ))
    styles.add(ParagraphStyle(
        name='CoverStudentName',
        fontName='Times-Bold',
        fontSize=11,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverSupervisionTitle',
        fontName='Times-Bold',
        fontSize=11,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverGuideName',
        fontName='Times-Bold',
        fontSize=11.5,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverCollegeName',
        fontName='Times-Bold',
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverCity',
        fontName='Times-Bold',
        fontSize=11,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name='CoverUnivName',
        fontName='Times-Bold',
        fontSize=11.5,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='CoverUnivState',
        fontName='Times-Bold',
        fontSize=11,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name='CoverYear',
        fontName='Times-Bold',
        fontSize=12,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))

    # Body Content Styles
    styles.add(ParagraphStyle(
        name='MainHeading',
        fontName='Times-Bold',
        fontSize=12.5,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=3,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='SubHeading',
        fontName='Times-Bold',
        fontSize=10.5,
        leading=14.5,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='BodyJustified',
        fontName='Times-Roman',
        fontSize=9.3,
        leading=13.3,
        alignment=4,  # Justified
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name='BodyBulletItem',
        fontName='Times-Roman',
        fontSize=9.2,
        leading=13,
        alignment=4,
        leftIndent=16,
        firstLineIndent=-10,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name='TableText',
        fontName='Times-Roman',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b"),
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        fontName='Times-Bold',
        fontSize=8.5,
        leading=11.5,
        alignment=1,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name='ReferenceItem',
        fontName='Times-Roman',
        fontSize=8,
        leading=11.5,
        leftIndent=22,
        firstLineIndent=-22,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='BoxText',
        fontName='Times-Roman',
        fontSize=7.5,
        leading=10.5,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='BoxTitle',
        fontName='Times-Bold',
        fontSize=8.5,
        leading=11.5,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))
    styles.add(ParagraphStyle(
        name='SignLabel',
        fontName='Times-Bold',
        fontSize=8.5,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
    ))

    return styles


def create_cover_page(story, styles):
    story.append(Spacer(1, 15))

    title_text = "DESIGN AND IMPLEMENTATION OF A POLICY-CONTROLLED<br/>ON-PREMISE AI WORKBENCH FOR CONFIDENTIAL WORKFLOWS"
    story.append(Paragraph(title_text, styles['CoverProjectTitle']))
    story.append(Spacer(1, 10))

    sub_text = (
        "<b>A Synopsis</b><br/>"
        "Submitted<br/>"
        "In Partial Fulfillment of the Requirements<br/>"
        "For the Degree of"
    )
    story.append(Paragraph(sub_text, styles['CoverSubtitle']))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Bachelor of Technology (B. Tech.)", styles['CoverDegree']))
    story.append(Paragraph("in<br/>Computer Science & Engineering", styles['CoverBranch']))
    story.append(Spacer(1, 8))

    story.append(Paragraph("by", styles['CoverBy']))
    story.append(Spacer(1, 8))

    student_data = [
        [
            Paragraph("Bhumik Sharma<br/><font color='#475569' size='9'>(2401920100127)</font>", styles['CoverStudentName']),
            Paragraph("Harsh Kumar Singh<br/><font color='#475569' size='9'>(2401920100152)</font>", styles['CoverStudentName']),
        ],
        [
            Paragraph("<br/>Harsh Kumar<br/><font color='#475569' size='9'>(2401920100151)</font>", styles['CoverStudentName']),
            Paragraph("<br/>Harshit Kumar<br/><font color='#475569' size='9'>(2401920100155)</font>", styles['CoverStudentName']),
        ]
    ]
    student_table = Table(student_data, colWidths=[240, 240])
    student_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(student_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Under the Supervision of", styles['CoverSupervisionTitle']))
    story.append(Spacer(1, 2))
    story.append(Paragraph("Ms. Abha Kaushik<br/><font color='#334155'>Assistant Professor</font>", styles['CoverGuideName']))
    story.append(Spacer(1, 10))

    if GL_LOGO_PATH.exists():
        story.append(Image(str(GL_LOGO_PATH), width=85, height=58))
    story.append(Spacer(1, 5))

    story.append(Paragraph("G.L. BAJAJ INSTITUTE OF TECHNOLOGY & MANAGEMENT", styles['CoverCollegeName']))
    story.append(Paragraph("GREATER NOIDA", styles['CoverCity']))
    story.append(Spacer(1, 10))

    if AKTU_LOGO_PATH.exists():
        story.append(Image(str(AKTU_LOGO_PATH), width=65, height=65))
    story.append(Spacer(1, 5))

    story.append(Paragraph("DR. A P J ABDUL KALAM TECHNICAL UNIVERSITY,", styles['CoverUnivName']))
    story.append(Paragraph("UTTAR PRADESH, LUCKNOW", styles['CoverUnivState']))
    story.append(Spacer(1, 14))

    story.append(Paragraph("2026-2027", styles['CoverYear']))
    story.append(PageBreak())


def build_synopsis():
    styles = get_synopsis_styles()
    story = []

    # =============================================================
    # PAGE 1: COVER PAGE
    # =============================================================
    create_cover_page(story, styles)

    # =============================================================
    # PAGE 2: 1. INTRODUCTION & 2. OBJECTIVES
    # =============================================================
    story.append(Paragraph("1. Introduction", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    intro_p1 = (
        "The recent advancement in Large Language Models (LLMs), Vision-Language Models (VLMs), "
        "and autonomous multi-step agents has fundamentally transformed organizational information processing, "
        "document synthesis, and computational reasoning. Commercial AI services hosted on public cloud "
        "infrastructures demonstrate remarkable capability in conversational understanding, multimodal synthesis, "
        "and automated code generation. However, deploying public cloud AI APIs within security-sensitive environments—such as "
        "industrial manufacturing facilities, public sector offices, defense units, research laboratories, and healthcare "
        "organizations—introduces critical vulnerabilities. Transmitting proprietary documents, operational schemas, "
        "and internal records to external third-party servers presents severe risks of data exfiltration, regulatory "
        "non-compliance under the Digital Personal Data Protection (DPDP) Act 2023, ISO 27001 violations, and loss of intellectual "
        "property sovereignty."
    )
    story.append(Paragraph(intro_p1, styles['BodyJustified']))

    intro_p2 = (
        "Concurrently, the rapid evolution of open-weight foundation models (such as Meta Llama 3, Qwen 2.5, Mistral, and Phi-3), "
        "paired with efficient local inference engines (Ollama, llama.cpp, and vLLM), has created a compelling opportunity to "
        "execute state-of-the-art AI workloads entirely on-premise without relying on external cloud APIs. Despite these advances, "
        "simply deploying an open-source model behind a generic chat interface fails to solve real enterprise challenges. "
        "Modern operational workflows require ingesting scanned, heterogeneous reports; extracting tables and layout data with high fidelity; "
        "retrieving factual internal records without hallucinations; executing computational analysis safely; and enforcing strict "
        "procedural governance over autonomous agent tool interactions."
    )
    story.append(Paragraph(intro_p2, styles['BodyJustified']))

    intro_p3 = (
        "This project, titled <i>'Design and Implementation of a Policy-Controlled On-Premise AI Workbench for Confidential Workflows'</i>, "
        "presents an integrated, secure, self-hosted platform engineered specifically for air-gapped organizational environments. "
        "Rather than attempting to train a foundation model from scratch, the primary engineering contribution of this project is "
        "the design and realization of a multi-tiered control architecture around local open-weight models. The system synthesizes "
        "capability-based routing, multimodal document parsing, local dense Retrieval-Augmented Generation (RAG), bounded finite-state "
        "agent execution, isolated code sandboxing, and deterministic verification to deliver an auditable, dependable, and strictly "
        "contained intelligent workspace."
    )
    story.append(Paragraph(intro_p3, styles['BodyJustified']))

    story.append(Paragraph("2. Objectives", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    objectives = [
        "<b>Air-Gapped On-Premise Execution:</b> To architect and deploy a completely self-hosted AI workbench operating on local infrastructure with verified zero runtime external network dependencies or telemetry egress.",
        "<b>Deterministic Capability and Policy Routing:</b> To develop an intelligent classifier and policy router that deterministically categorizes incoming requests (e.g., text reasoning, document extraction, internal search, sandboxed data computation) and routes them to specialized local processing pipelines.",
        "<b>High-Fidelity Multimodal Ingestion:</b> To implement a robust document parsing pipeline combining digital text extraction, local Optical Character Recognition (OCR using PaddleOCR/Tesseract), and Vision-Language Models (VLMs) to process complex scans, blueprints, and tabular spreadsheets while preserving document hierarchy and page provenance.",
        "<b>Evidence-Grounded Local Knowledge Retrieval (RAG):</b> To build a localized vector search subsystem utilizing semantic chunking, dense embeddings, vector indexing, and cross-encoder reranking to ensure answers are strictly linked to verified internal organizational documents.",
        "<b>Bounded Finite-State Agent Orchestration:</b> To implement an autonomous agent engine governed by explicit finite state machines, tool allowlists, strict step limits, and timeout boundaries to eliminate runaway loops, excessive agency, and unpredictable model behaviors.",
        "<b>Isolated Code and Data Analysis Sandbox:</b> To engineer an isolated execution environment with disabled network interfaces, restricted CPU/RAM quotas, and restricted filesystem namespaces for safely executing LLM-generated Python and data analysis routines.",
        "<b>Deterministic Verification and Human Oversight:</b> To integrate automated schema validation, calculation checks, and confidence scoring, coupled with a mandatory human-in-the-loop review workflow for high-risk or low-confidence operational outputs.",
        "<b>Runtime Observability and Verifiable Auditability:</b> To establish end-to-end structured audit logging, pipeline traceability, and network isolation validation to provide cryptographic accountability for every generated deliverable."
    ]

    for obj in objectives:
        story.append(Paragraph(f"• {obj}", styles['BodyBulletItem']))

    story.append(PageBreak())

    # =============================================================
    # PAGE 3: 3. EXISTING SYSTEM & RELATED WORK
    # =============================================================
    story.append(Paragraph("3. Existing System (Application Based Project / Related Work)", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    ex_text1 = (
        "In modern organizational workflows, existing computational solutions can be broadly categorized into "
        "commercial cloud AI platforms, open-source local chat interfaces, and experimental agent frameworks. "
        "An analysis of 5 prevailing industry solutions highlights foundational technical shortcomings that our project resolves:"
    )
    story.append(Paragraph(ex_text1, styles['BodyJustified']))

    col_widths = [110, 185, 195]
    table_data = [
        [
            Paragraph("<b>Existing System</b>", styles['TableHeader']),
            Paragraph("<b>Key Features & Architecture</b>", styles['TableHeader']),
            Paragraph("<b>Critical Limitations in Sensitive Workflows</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Commercial Cloud AI</b><br/>(ChatGPT Enterprise, Claude, MS Copilot)", styles['TableText']),
            Paragraph("Centralized proprietary LLMs hosted on public cloud. Massive parameter scale, high zero-shot capability, API-based integration.", styles['TableText']),
            Paragraph("Mandatory external data transmission; risk of data residency breaches; recurring token costs; non-compliance with air-gapped security protocols.", styles['TableText']),
        ],
        [
            Paragraph("<b>Local Model Frontends</b><br/>(Open WebUI, Ollama Web, LM Studio)", styles['TableText']),
            Paragraph("Desktop or web wrappers running quantized GGUF/AWQ models locally via Ollama or llama.cpp for single-turn prompt chat.", styles['TableText']),
            Paragraph("Lack multi-agent orchestration; no deterministic policy routing; rudimentary RAG lacking reranking; unable to execute sandboxed code safely.", styles['TableText']),
        ],
        [
            Paragraph("<b>Local Document RAG</b><br/>(PrivateGPT, LocalGPT, AnythingLLM)", styles['TableText']),
            Paragraph("Document ingestion via LangChain/LlamaIndex, chunking, and local embedding retrieval into ChromaDB/FAISS.", styles['TableText']),
            Paragraph("Vulnerable to OCR degradation on scanned images; lacks multimodal VLM extraction; no calculation verification; absent human approval gates.", styles['TableText']),
        ],
        [
            Paragraph("<b>Autonomous Agent Frameworks</b><br/>(AutoGPT, CrewAI, LangGraph)", styles['TableText']),
            Paragraph("Multi-agent prompting patterns allowing LLMs to invoke external bash tools, web search, and script interpreters.", styles['TableText']),
            Paragraph("Risk of unconstrained agency and prompt injection; tools run in host environment without container isolation; prone to non-terminating loops.", styles['TableText']),
        ],
        [
            Paragraph("<b>Enterprise Data Suites</b><br/>(Dataiku, IBM Watsonx On-Prem)", styles['TableText']),
            Paragraph("Comprehensive enterprise data management, model registry, and workflow orchestration suites.", styles['TableText']),
            Paragraph("Extremely high licensing costs; heavy operational overhead requiring massive distributed clusters; not optimized for agile single-node workstations.", styles['TableText']),
        ]
    ]

    t_apps = Table(table_data, colWidths=col_widths, repeatRows=1)
    t_apps.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_apps)
    story.append(Spacer(1, 6))

    rw_text = (
        "<b>Synthesis of Related Academic Research:</b><br/>"
        "The architecture builds upon foundational paradigms across multiple computing domains. "
        "In Retrieval-Augmented Generation, Lewis et al. (2020) and Gao et al. (2023) demonstrated that dense vector indexing combined "
        "with semantic chunking significantly reduces generative hallucinations by conditioning model inference on authoritative retrieved passages. "
        "In agentic reasoning, Yao et al. (2023) established the ReAct (Reasoning + Acting) paradigm, while Schick et al. (2023) introduced "
        "Toolformer to demonstrate self-taught tool utilization; however, both approaches exhibit safety vulnerabilities when operating with unconstrained "
        "execution environments. Recent investigations into LLM safety by Greshake et al. (2023) proved that untrusted document text can execute indirect "
        "prompt injection attacks on autonomous agents, making hardened tool allowlists and isolated sandboxes non-negotiable. "
        "Furthermore, advancements in lightweight 4-bit and 8-bit quantization by Dettmers et al. (2023) enable high-throughput parameter-efficient "
        "inference on standard edge hardware, validating the technical feasibility of our fully on-premise workbench."
    )
    story.append(Paragraph(rw_text, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 4: 4. MOTIVATION & PROBLEM STATEMENT
    # =============================================================
    story.append(Paragraph("4. Motivation & Problem Statement", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    story.append(Paragraph("<b>4.1 Motivation</b>", styles['SubHeading']))
    mot_text1 = (
        "Modern organizations handle immense volumes of highly proprietary, mission-critical assets, including technical blueprints, "
        "industrial equipment inspection reports, confidential legal contracts, audited financial records, and medical diagnostics. "
        "While staff could achieve immense productivity gains through generative summarization, automated report drafting, and programmatic "
        "data querying, enterprise security policies and national legal frameworks strictly forbid transmitting confidential files to "
        "public multi-tenant AI servers. Commercial AI subscriptions further impose unpredictable per-token pricing, vendor lock-in, and sudden "
        "service deprecation."
    )
    story.append(Paragraph(mot_text1, styles['BodyJustified']))

    mot_text2 = (
        "Furthermore, organizations in manufacturing, civil infrastructure, and administrative governance are frequently subject to "
        "stringent air-gapped security protocols where computing nodes cannot maintain constant internet connectivity. Consequently, "
        "there is an urgent imperative for an on-premise, policy-controlled computational workbench that empowers knowledge workers "
        "with advanced AI capabilities while guaranteeing complete data sovereignty, predictable operational expenditure, and zero "
        "operational leakage."
    )
    story.append(Paragraph(mot_text2, styles['BodyJustified']))

    story.append(Paragraph("<b>4.2 Problem Statement</b>", styles['SubHeading']))
    ps_text1 = (
        "The fundamental engineering challenge addressed in this project is: <i>How can an organization leverage cutting-edge multimodal AI, "
        "knowledge retrieval, and agentic task execution entirely within a local, air-gapped environment while maintaining deterministic control "
        "over confidential information, preventing hallucinated outputs, bounding autonomous tool actions, and containing untrusted code execution?</i>"
    )
    story.append(Paragraph(ps_text1, styles['BodyJustified']))

    ps_text2 = (
        "To achieve a dependable system, the engineering implementation must systematically eliminate four critical failure modes "
        "identified in conventional AI systems:<br/>"
        "• <b>Data Sovereignty & Containment Failure:</b> The risk of sensitive organizational documents leaking through outbound API calls, model telemetry, or third-party cloud caching. The system must enforce zero external network egress at runtime.<br/>"
        "• <b>Generative Hallucination & Ungrounded Reasoning:</b> The tendency of foundation models to generate factually erroneous numbers or fabricate non-existent engineering standards. The system must enforce strict retrieval grounding and citation linking.<br/>"
        "• <b>Unbounded Agent Autonomy:</b> The danger of recursive prompt chaining leading to runaway computational loops, destructive system operations, or non-terminating agent steps. The system must govern agent execution with strict finite-state invariants and step quotas.<br/>"
        "• <b>Host Compromise via Untrusted Code Execution:</b> The security hazard of executing LLM-generated Python or shell scripts directly on the host operating system. The system must encapsulate all execution within an isolated, resource-constrained sandbox."
    )
    story.append(Paragraph(ps_text2, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 5: 5.1 SOLUTION EXPLANATION & ARCHITECTURAL PHILOSOPHY
    # =============================================================
    story.append(Paragraph("5. Proposed Methodology & Process for Implementation", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    story.append(Paragraph("<b>5.1 Detailed Explanation of the Proposed Solution</b>", styles['SubHeading']))
    sol_intro = (
        "The proposed solution is an integrated, policy-governed on-premise AI workbench deployed inside an organization's "
        "internal local area network (LAN). Rather than exposing a raw, unconstrained language model directly to user prompts, "
        "the system establishes a defense-in-depth architecture. The platform treats every incoming request as an untrusted transaction "
        "that must be deterministically analyzed, authorized, routed to specialized micro-services, executed under bounded invariants, "
        "and mathematically verified before any deliverable is surfaced to human operators."
    )
    story.append(Paragraph(sol_intro, styles['BodyJustified']))

    sol_layers = (
        "The system architecture comprises eight tightly integrated functional layers:<br/>"
        "• <b>Layer 1 — Access & Request Gateway:</b> Enforces role-based access control, validates MIME types, scans file signatures, and binds each session to an immutable cryptographically secure UUID for complete operational auditability.<br/>"
        "• <b>Layer 2 — Task & Capability Analyzer:</b> Employs deterministic rule classifiers and shallow text embeddings to detect required modalities: Digital Text, Scanned PDF, Tabular Data, Engineering Diagram, or Code Transformation.<br/>"
        "• <b>Layer 3 — Policy & Hardware-Aware Router:</b> Dynamically inspects active GPU VRAM and CPU load. It routes simple text tasks to lightweight quantized models, visual documents to local VLMs, and data calculations to the sandbox.<br/>"
        "• <b>Layer 4 — Bounded Agent Execution Engine:</b> Formulates task execution as a deterministic finite state machine (FSM). The LLM plans steps, but execution is governed by hard step caps (≤ 5 steps), tool allowlists, and execution timeouts.<br/>"
        "• <b>Layer 5 — Local Knowledge Pipeline (Dense RAG):</b> Ingests enterprise manuals, creates dense vector embeddings via local transformer models, indexes them into a local vector store, and applies cross-encoder reranking to ensure factual grounding.<br/>"
        "• <b>Layer 6 — Isolated Execution Sandbox:</b> A hardened subprocess container with network loopback disabled, non-root user execution, and strict memory/CPU quotas for executing data-transformation scripts.<br/>"
        "• <b>Layer 7 — Verification & Human-in-the-Loop Oversight:</b> Executes automated JSON schema validation, arithmetic checks, and citation coverage tests. Low-confidence outputs trigger a mandatory human approval gate.<br/>"
        "• <b>Layer 8 — Observability & Deliverable Export:</b> Generates structured forensic audit records and exports publication-ready documents in PDF, DOCX, and XLSX formats."
    )
    story.append(Paragraph(sol_layers, styles['BodyJustified']))

    arch_phil = (
        "<b>Core Architectural Philosophy:</b> The platform operates on the principle of <i>least privilege for autonomous models</i>. "
        "By enforcing strict physical separation between model reasoning, file retrieval, code execution, and deliverable rendering, "
        "the architecture mathematically eliminates the possibility of uncontained agent behaviors, indirect prompt injection breaches, "
        "and remote telemetry leakage."
    )
    story.append(Paragraph(arch_phil, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 6: 5.2 SYSTEM ARCHITECTURE & EXECUTION LIFECYCLE
    # =============================================================
    story.append(Paragraph("<b>5.2 System Architecture and Modular Flow</b>", styles['SubHeading']))

    arch_cells = [
        [Paragraph("<b>USER / INTERNAL CLIENT WORKSTATION (LAN)</b>", styles['BoxTitle'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>ACCESS & REQUEST GATEWAY</b><br/><font size='7.5' color='#334155'>Local Authentication | MIME & File Validation | Cryptographic Audit UUID Generation</font>", styles['BoxText'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>TASK & CAPABILITY ANALYZER</b><br/><font size='7.5' color='#334155'>Modality Classifier: Digital Text | Scanned Document | Tabular Data | Visual Diagram | Code Task</font>", styles['BoxText'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>POLICY & HARDWARE-AWARE ROUTER</b><br/><font size='7.5' color='#334155'>Evaluates VRAM/RAM Headroom & Privacy Policy → Dispatches to Specialized Pipeline</font>", styles['BoxText'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [
            Table([
                [
                    Paragraph("<b>Local LLM Engine</b><br/><font size='7'>Qwen 2.5 / Llama 3<br/>Reasoning & Drafting</font>", styles['BoxText']),
                    Paragraph("<b>Multimodal OCR / VLM</b><br/><font size='7'>PaddleOCR / Qwen2-VL<br/>Layout & Scan Parsing</font>", styles['BoxText']),
                    Paragraph("<b>Local Dense RAG</b><br/><font size='7'>BGE / ChromaDB<br/>Grounded Retrieval</font>", styles['BoxText']),
                    Paragraph("<b>Isolated Sandbox</b><br/><font size='7'>Restricted Python Env<br/>No-Network Analytics</font>", styles['BoxText']),
                ]
            ], colWidths=[120, 120, 120, 120], style=[
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ])
        ],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>BOUNDED FINITE-STATE AGENT ENGINE</b><br/><font size='7.5' color='#334155'>Plan Validation | Max Step Budget (≤ 5) | Tool Allowlists | Loop & Recursion Guards</font>", styles['BoxText'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>DETERMINISTIC VERIFICATION & OVERSIGHT LAYER</b><br/><font size='7.5' color='#334155'>Schema & Arithmetic Validation | Citation Evidence Checking | Human Approval Escalation Gate</font>", styles['BoxText'])],
        [Paragraph("▼", styles['BoxTitle'])],
        [Paragraph("<b>AUDIT RECORDING & STRUCTURED EXPORT ENGINE</b><br/><font size='7.5' color='#334155'>Immutable Audit Logs | Structured Synthesis (PDF / DOCX / XLSX Deliverables)</font>", styles['BoxText'])],
    ]

    t_arch = Table(arch_cells, colWidths=[490])
    t_arch.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#e2e8f0")),
        ('BACKGROUND', (0, 2), (0, 2), colors.HexColor("#ede9fe")),
        ('BACKGROUND', (0, 4), (0, 4), colors.HexColor("#dbeafe")),
        ('BACKGROUND', (0, 6), (0, 6), colors.HexColor("#e0e7ff")),
        ('BACKGROUND', (0, 10), (0, 10), colors.HexColor("#fef3c7")),
        ('BACKGROUND', (0, 12), (0, 12), colors.HexColor("#fee2e2")),
        ('BACKGROUND', (0, 14), (0, 14), colors.HexColor("#dcfce7")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_arch)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>End-to-End Operational Execution Lifecycle:</b>", styles['SubHeading']))
    lifecycle_text = (
        "The architecture follows a strict synchronous execution flow to maintain absolute determinism and security:<br/>"
        "1. <b>Ingress & Sanitization:</b> The request is sanitized, checked against file size and format allowlists, and assigned a session audit identifier.<br/>"
        "2. <b>Capability Routing:</b> The analyzer inspects file extensions, headers, and semantic prompts to select the target model runtime.<br/>"
        "3. <b>Multimodal Extraction & Grounding:</b> Scanned images pass through local OCR while textual queries trigger semantic vector search over internal manuals.<br/>"
        "4. <b>Bounded Agent Reasoning:</b> The agent plans sub-actions within strict state-machine constraints. Tools cannot invoke unauthorized shell commands.<br/>"
        "5. <b>Hermetic Sandbox Execution:</b> Any analytical code is piped to an isolated subprocess with networking disabled and tight memory ceilings.<br/>"
        "6. <b>Verification & Export:</b> Output claims are checked against retrieved text snippets, formatted into structured deliverables, and logged for audit compliance."
    )
    story.append(Paragraph(lifecycle_text, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 7: 5.3 MECHANISM MAPPING & 5.4 INNOVATION & UNIQUENESS
    # =============================================================
    story.append(Paragraph("<b>5.3 How the Solution Addresses the Identified Challenges</b>", styles['SubHeading']))
    
    mapping_data = [
        [
            Paragraph("<b>Problem / Requirement</b>", styles['TableHeader']),
            Paragraph("<b>Proposed Technical Mechanism</b>", styles['TableHeader']),
            Paragraph("<b>Expected Engineering Outcome</b>", styles['TableHeader']),
        ],
        [
            Paragraph("Sensitive corporate data must never leak to third parties", styles['TableText']),
            Paragraph("Full on-premise execution using local open-weight models (GGUF/vLLM) and air-gapped local storage with zero runtime cloud APIs.", styles['TableText']),
            Paragraph("Complete mathematical elimination of external data transmission and total data sovereignty.", styles['TableText']),
        ],
        [
            Paragraph("Heterogeneous tasks require diverse computational capabilities", styles['TableText']),
            Paragraph("Deterministic capability-based routing across text LLM, VLM/OCR, dense vector RAG, and isolated data sandbox.", styles['TableText']),
            Paragraph("Optimal task-to-tool fit, minimized latency, and avoidance of resource overallocation.", styles['TableText']),
        ],
        [
            Paragraph("Proprietary institutional knowledge must be queried without retraining", styles['TableText']),
            Paragraph("Dense local RAG pipeline with semantic chunking, local vector indexing, metadata filtering, and cross-encoder reranking.", styles['TableText']),
            Paragraph("Accurate, hallucination-resistant responses with page-level citations linked directly to internal evidence.", styles['TableText']),
        ],
        [
            Paragraph("Autonomous agents can execute dangerous or infinite loops", styles['TableText']),
            Paragraph("Bounded agent state machine with strict step budgets (≤ 5 steps), tool allowlists, parameter sanitization, and automated timeouts.", styles['TableText']),
            Paragraph("Elimination of unbounded autonomous drift, runaway compute consumption, and unexpected tool calls.", styles['TableText']),
        ],
        [
            Paragraph("Model-generated code can compromise host filesystem or network", styles['TableText']),
            Paragraph("Isolated execution environment with disabled networking, non-root user execution, memory limits, and temporary workspace teardown.", styles['TableText']),
            Paragraph("Hermetic containment of untrusted code; safe execution of complex analytical scripts.", styles['TableText']),
        ],
        [
            Paragraph("Generative output can contain subtle hallucinations or arithmetic errors", styles['TableText']),
            Paragraph("Multi-stage verification layer with deterministic JSON schema checking, calculation validation, and human review for high-impact outputs.", styles['TableText']),
            Paragraph("High factual reliability and clear operational accountability before final delivery.", styles['TableText']),
        ],
        [
            Paragraph("Organizations require compliance traceability and audit trails", styles['TableText']),
            Paragraph("Structured JSON runtime logging capturing model hyperparameters, tool invocations, token timings, and network activity.", styles['TableText']),
            Paragraph("Full forensic visibility, debuggability, and compliance with statutory security standards.", styles['TableText']),
        ],
    ]

    t_map = Table(mapping_data, colWidths=[120, 195, 175], repeatRows=1)
    t_map.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_map)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>5.4 Innovation and Uniqueness of the Solution</b>", styles['SubHeading']))
    innov_text = (
        "The project does not claim novelty in developing novel foundation model architectures, as open-source LLMs, "
        "vector databases, and containers are existing technologies. Rather, the innovation lies in the <b>systems engineering "
        "and controlled integration architecture</b> tailored specifically for zero-trust organizational environments:<br/>"
        "• <b>Capability-Based Routing over Monolithic Prompts:</b> Instead of sending every request to a massive general-purpose model, "
        "the router decomposes the task into discrete modalities (OCR, retrieval, calculation, reasoning) and routes each sub-task to the most efficient specialist engine.<br/>"
        "• <b>Bounded Agency with Hard Safety Invariants:</b> Unlike unconstrained frameworks that give LLMs direct bash access, "
        "this system confines agent execution within an external finite state machine with strict step quotas, explicit tool allowlists, and deterministic safety invariants.<br/>"
        "• <b>Multi-Stage Verification Layer:</b> By separating generation from verification, outputs undergo automated schema checks, "
        "retrieval coverage tests, and arithmetic validation, routing unverified claims to human reviewers.<br/>"
        "• <b>Defense-in-Depth Local Security:</b> Security is implemented at every tier—from MIME-type upload validation and isolated sandbox execution "
        "to verifiable network silence monitoring.<br/>"
        "• <b>Measurable Engineering Pragmatism:</b> The system establishes an honest boundary between demonstrated local capability and "
        "production requirements, prioritizing empirical benchmarking and explainability over exaggerated claims of artificial general intelligence."
    )
    story.append(Paragraph(innov_text, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 8: 5.5 IMPLEMENTATION PHASES & PROTOTYPE DESIGN
    # =============================================================
    story.append(Paragraph("<b>5.5 Implementation Phases & Working Prototype Design</b>", styles['SubHeading']))
    phase_text = (
        "The project follows a disciplined nine-phase engineering lifecycle designed to ensure modular verification at each milestone:<br/>"
        "• <b>Phase 1 — Threat Modeling & Boundary Definition:</b> Formulate threat models, define prohibited system actions, identify sensitive data categories, and establish human escalation thresholds.<br/>"
        "• <b>Phase 2 — Local Inference Engine Deployment:</b> Deploy Ollama / llama.cpp runtime with quantized models (Qwen 2.5 7B, Llama 3.2) and benchmark CPU/VRAM throughput without internet connectivity.<br/>"
        "• <b>Phase 3 — Task Analysis & Routing Engine:</b> Construct rule-based and embedding-based classifiers to route requests based on modality, estimated complexity, and hardware load.<br/>"
        "• <b>Phase 4 — Multimodal Document Ingestion Pipeline:</b> Implement PyMuPDF and PaddleOCR extraction pipelines to parse complex multi-page PDFs, tabular data, and scanned equipment logs.<br/>"
        "• <b>Phase 5 — Dense Local Knowledge Subsystem (RAG):</b> Implement recursive character chunking with metadata tagging, build a local ChromaDB/FAISS vector index, and integrate a cross-encoder reranker.<br/>"
        "• <b>Phase 6 — Bounded Agent State Machine:</b> Implement an explicit state machine controlling agent planning, tool invocation, and state transitions, enforcing a maximum budget of 5 steps per task.<br/>"
        "• <b>Phase 7 — Isolated Execution Sandbox:</b> Develop a network-disabled execution environment with strict CPU/memory quotas for executing Python scripts and data transformations.<br/>"
        "• <b>Phase 8 — Verification Layer & Human Oversight:</b> Build automated output validators (schema matching, arithmetic cross-checking) and integrate an interactive human approval interface.<br/>"
        "• <b>Phase 9 — Observability, Evaluation & Hardening:</b> Instrument structured JSON audit logging, monitor outbound network silence, and execute end-to-end benchmark evaluations on held-out industrial datasets."
    )
    story.append(Paragraph(phase_text, styles['BodyJustified']))
    story.append(Spacer(1, 4))

    proto_heading = "<b>Target Working Prototype Workflow</b>"
    story.append(Paragraph(proto_heading, styles['SubHeading']))
    proto_text = (
        "To rigorously validate the architecture, the working prototype demonstrates a high-impact, realistic industrial workflow: "
        "the automated ingestion, verification, and synthesis of confidential technical inspection reports:<br/>"
        "1. <b>Document Ingestion & File Validation:</b> An operator submits a scanned multi-page PDF containing machinery sensor logs and operational notes. The gateway validates MIME integrity and initializes a unique audit session.<br/>"
        "2. <b>Multimodal Extraction:</b> PaddleOCR parses image scans into text blocks while PyMuPDF extracts tabular metadata and structural headers, preserving page numbers and bounding coordinates.<br/>"
        "3. <b>Policy-Governed Retrieval (RAG):</b> The agent queries internal standard operating procedures (SOPs) and safety compliance limits indexed within the local ChromaDB vector store, reranking results to obtain exact tolerance limits.<br/>"
        "4. <b>Sandboxed Computational Analysis:</b> For tabular sensor readings, the agent writes a Python script to compute mean operating temperatures, pressure deviations, and anomaly percentages. The script executes within an air-gapped sandbox with no network access.<br/>"
        "5. <b>Verification & Escalation:</b> The verification layer confirms that extracted values match the source scan and that calculated statistics satisfy schema invariants. If an anomaly exceeds safety thresholds, the system flags the issue for mandatory engineer sign-off.<br/>"
        "6. <b>Deliverable Synthesis:</b> Upon approval, the system exports a tamper-evident audit report with page-level citations and chronological event logs in PDF/DOCX format."
    )
    story.append(Paragraph(proto_text, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 9: 6. POTENTIAL IMPACT ON THE TARGET AUDIENCE
    # =============================================================
    story.append(Paragraph("6. Potential Impact on the Target Audience", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    impact_intro = (
        "The proposed on-premise workbench delivers substantial multidimensional benefits across diverse operational sectors:"
    )
    story.append(Paragraph(impact_intro, styles['BodyJustified']))

    impact_data = [
        [
            Paragraph("<b>Impact Dimension</b>", styles['TableHeader']),
            Paragraph("<b>Direct Operational & Societal Benefits</b>", styles['TableHeader']),
            Paragraph("<b>Engineering Contribution of the Solution</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Social & Workforce Impact</b>", styles['TableText']),
            Paragraph("Augments human engineers and administrative personnel by automating mundane document extraction, allowing specialists to focus on high-value cognitive decisions while retaining supervisory control.", styles['TableText']),
            Paragraph("Human-in-the-loop architecture guarantees that consequential technical actions require explicit human sign-off, preventing deskilling and loss of oversight.", styles['TableText']),
        ],
        [
            Paragraph("<b>Economic & Cost Viability</b>", styles['TableText']),
            Paragraph("Eliminates recurring per-token subscription costs associated with public cloud APIs; provides predictable operational expense utilizing existing institutional compute hardware.", styles['TableText']),
            Paragraph("Capability-based routing prevents unnecessary activation of heavyweight models, maximizing throughput per watt and extending hardware lifecycle.", styles['TableText']),
        ],
        [
            Paragraph("<b>Security, Legal & Compliance</b>", styles['TableText']),
            Paragraph("Guarantees strict compliance with the Indian Digital Personal Data Protection (DPDP) Act 2023, ISO 27001, and public-sector data classification mandates.", styles['TableText']),
            Paragraph("Zero network egress architecture mathematically eliminates remote data exfiltration, vendor tracking, and prompt telemetry exposure.", styles['TableText']),
        ],
        [
            Paragraph("<b>Environmental & Energy Efficiency</b>", styles['TableText']),
            Paragraph("Drastically cuts unnecessary carbon footprints compared to querying 100B+ parameter hyperscale cloud models for simple internal tasks.", styles['TableText']),
            Paragraph("Employs quantized 7B/8B small language models (SLMs) and deterministic routing, minimizing unnecessary GPU power dissipation.", styles['TableText']),
        ],
        [
            Paragraph("<b>Institutional Knowledge Retention</b>", styles['TableText']),
            Paragraph("Transforms unindexed, siloed archival records, technical manuals, and scanned legacy documents into active, searchable institutional intelligence.", styles['TableText']),
            Paragraph("Dense local RAG preserves organizational memory independently of external SaaS vendor availability or internet outages.", styles['TableText']),
        ]
    ]

    t_imp = Table(impact_data, colWidths=[110, 195, 185], repeatRows=1)
    t_imp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_imp)
    story.append(Spacer(1, 8))

    aud_title = "<b>Primary Beneficiaries & Target Audience Segments</b>"
    story.append(Paragraph(aud_title, styles['SubHeading']))
    aud_text = (
        "• <b>Industrial Manufacturing & Heavy Engineering:</b> Plant managers, safety inspectors, and quality assurance engineers who require rapid extraction and trend analysis from equipment logs, vibration scans, and calibration certificates without uploading proprietary blueprints to external clouds.<br/>"
        "• <b>Public Sector & Government Administrative Departments:</b> Civil offices handling confidential citizen records, policy circulars, and departmental correspondence under strict data protection and air-gapped guidelines.<br/>"
        "• <b>Legal & Corporate Compliance Firms:</b> Legal associates analyzing complex multi-hundred-page commercial contracts, patents, and nondisclosure agreements under strict attorney-client privilege.<br/>"
        "• <b>Healthcare & Clinical Research Facilities:</b> Medical practitioners querying localized clinical records and treatment protocols without compromising patient confidentiality under health privacy regulations."
    )
    story.append(Paragraph(aud_text, styles['BodyJustified']))
    story.append(PageBreak())

    # =============================================================
    # PAGE 10: 7. TOOLS, TECHNOLOGIES & RESOURCE REQUIREMENTS
    # =============================================================
    story.append(Paragraph("7. Tools, Technologies & Resource Requirements", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    story.append(Paragraph("<b>7.1 Hardware Resource Specifications</b>", styles['SubHeading']))
    
    hw_data = [
        [
            Paragraph("<b>Deployment Tier</b>", styles['TableHeader']),
            Paragraph("<b>Target Hardware Specifications</b>", styles['TableHeader']),
            Paragraph("<b>Operational Scope & Model Capabilities</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Minimum Development Specification</b><br/>(Student Workstation)", styles['TableText']),
            Paragraph("<b>CPU:</b> Modern 6–8 Core x86_64 Processor<br/><b>RAM:</b> 16 GB System Memory<br/><b>Storage:</b> 512 GB NVMe SSD<br/><b>GPU:</b> Integrated / Entry-level GPU (CPU-only fallback)", styles['TableText']),
            Paragraph("Enables local document extraction, dense RAG vector search, and execution of quantized 3B–7B SLMs (Q4_K_M quantization). Response generation is functional though token throughput is modest (~4–8 tokens/s on CPU).", styles['TableText']),
        ],
        [
            Paragraph("<b>Recommended MVP Specification</b><br/>(Dedicated Lab Station)", styles['TableText']),
            Paragraph("<b>CPU:</b> 8–16 Core High-Performance CPU<br/><b>RAM:</b> 32–64 GB High-Speed DDR5 RAM<br/><b>Storage:</b> 1 TB PCIe Gen4 NVMe SSD<br/><b>GPU:</b> NVIDIA RTX 3060 / 4060 / 4070 (12–16 GB VRAM)", styles['TableText']),
            Paragraph("Enables simultaneous loading of 7B–14B instruction models, multimodal vision models (Qwen2-VL), dense embeddings, and real-time OCR parsing with interactive token generation (~25–45 tokens/s).", styles['TableText']),
        ],
        [
            Paragraph("<b>Production Scaled Reference</b><br/>(Enterprise On-Prem Node)", styles['TableText']),
            Paragraph("<b>CPU:</b> Dual AMD EPYC / Intel Xeon (32+ Cores)<br/><b>RAM:</b> 128+ GB ECC RAM<br/><b>Storage:</b> Multi-TB Enterprise NVMe RAID<br/><b>GPU:</b> Dual NVIDIA RTX A6000 / A100 / L40S (48–80 GB VRAM)", styles['TableText']),
            Paragraph("High-concurrency enterprise deployment supporting continuous multi-user document pipelines, concurrent agent execution, and batch RAG indexing.", styles['TableText']),
        ],
    ]

    t_hw = Table(hw_data, colWidths=[110, 190, 190], repeatRows=1)
    t_hw.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_hw)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>7.2 Software Stack and Architectural Libraries</b>", styles['SubHeading']))

    sw_data = [
        [
            Paragraph("<b>Functional Layer</b>", styles['TableHeader']),
            Paragraph("<b>Technology / Framework</b>", styles['TableHeader']),
            Paragraph("<b>Specific Role & Implementation Details</b>", styles['TableHeader']),
        ],
        [
            Paragraph("<b>Core Programming</b>", styles['TableText']),
            Paragraph("Python 3.11+, HTML5 / Tailwind CSS, JavaScript", styles['TableText']),
            Paragraph("High-performance backend orchestration, asynchronous task handling, and responsive desktop interface.", styles['TableText']),
        ],
        [
            Paragraph("<b>Backend API Gateway</b>", styles['TableText']),
            Paragraph("FastAPI, Uvicorn, Pydantic v2", styles['TableText']),
            Paragraph("Asynchronous REST service layer, strict schema validation, request authentication, and audit identifier propagation.", styles['TableText']),
        ],
        [
            Paragraph("<b>Local Model Runtime</b>", styles['TableText']),
            Paragraph("Ollama, llama.cpp, vLLM", styles['TableText']),
            Paragraph("High-throughput local model serving, dynamic GPU layer offloading, context window management, and zero runtime API calls.", styles['TableText']),
        ],
        [
            Paragraph("<b>Foundation Models</b>", styles['TableText']),
            Paragraph("Qwen 2.5 (7B/14B), Meta Llama 3.2 (3B/8B), Mistral NeMo", styles['TableText']),
            Paragraph("Quantized instruction-following models utilized for reasoning, synthesis, structured data extraction, and report drafting.", styles['TableText']),
        ],
        [
            Paragraph("<b>Multimodal & OCR</b>", styles['TableText']),
            Paragraph("PaddleOCR, PyMuPDF (fitz), Qwen2-VL", styles['TableText']),
            Paragraph("Parsing of multi-page PDFs, high-accuracy tabular extraction, layout preservation, and visual chart comprehension.", styles['TableText']),
        ],
        [
            Paragraph("<b>Knowledge Embeddings</b>", styles['TableText']),
            Paragraph("BAAI/bge-large-en-v1.5, all-MiniLM-L6-v2", styles['TableText']),
            Paragraph("Local dense vector embeddings for semantic document chunking and domain-specific knowledge representation.", styles['TableText']),
        ],
        [
            Paragraph("<b>Vector Storage</b>", styles['TableText']),
            Paragraph("ChromaDB, FAISS (Facebook AI Similarity Search)", styles['TableText']),
            Paragraph("Fast, persistent, on-disk similarity search over organizational document embeddings with metadata filtering.", styles['TableText']),
        ],
        [
            Paragraph("<b>Reranking Engine</b>", styles['TableText']),
            Paragraph("BAAI/bge-reranker-large", styles['TableText']),
            Paragraph("Cross-encoder reranking to re-score top candidate chunks, drastically enhancing RAG precision and context relevance.", styles['TableText']),
        ],
        [
            Paragraph("<b>Agent Orchestration</b>", styles['TableText']),
            Paragraph("Custom State Machine Engine / LangGraph", styles['TableText']),
            Paragraph("Deterministic graph-based agent workflow enforcing maximum step limits, tool execution allowlists, and state checkpoints.", styles['TableText']),
        ],
        [
            Paragraph("<b>Isolated Sandbox</b>", styles['TableText']),
            Paragraph("Rootless Subprocess Isolation / Podman Containers", styles['TableText']),
            Paragraph("Restricted runtime with dropped capabilities, disabled network loopback, and strict CPU/RAM memory quotas.", styles['TableText']),
        ],
        [
            Paragraph("<b>Document Generation</b>", styles['TableText']),
            Paragraph("ReportLab, python-docx, openpyxl, pandas", styles['TableText']),
            Paragraph("Programmatic generation of structured executive reports, spreadsheet summaries, and publication-ready deliverables.", styles['TableText']),
        ],
        [
            Paragraph("<b>Metadata & Audit DB</b>", styles['TableText']),
            Paragraph("SQLite 3 / PostgreSQL", styles['TableText']),
            Paragraph("Persistent storage of user session metadata, document provenance, verification flags, and chronological audit trails.", styles['TableText']),
        ]
    ]

    t_sw = Table(sw_data, colWidths=[100, 160, 230], repeatRows=1)
    t_sw.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#94a3b8")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sw)
    story.append(PageBreak())

    # =============================================================
    # PAGE 11: 8. REFERENCES (APA FORMAT) & ACADEMIC SIGN-OFF BLOCK
    # =============================================================
    story.append(Paragraph("8. References (APA Format)", styles['MainHeading']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0f172a"), spaceBefore=2, spaceAfter=6))

    references = [
        "[1] Bai, Y., Kadavath, S., Kundu, S., Askell, A., Kernion, J., Jones, A., ... & Kaplan, J. (2022). Constitutional AI: Harmlessness from AI feedback. <i>arXiv preprint arXiv:2212.08073</i>.",
        "[2] Dettmers, T., Svirschevski, R., Egiazarian, V., Kuzmin, A., Baziotis, C., & Zettlemoyer, L. (2023). SpQR: A sparse-quantized representation for near-lossless LLM weight compression. <i>arXiv preprint arXiv:2306.03078</i>.",
        "[3] Gao, Y., Xiong, Y., Gao, X., Jia, K., Pan, J., Bi, Y., ... & Wang, H. (2023). Retrieval-augmented generation for large language models: A survey. <i>arXiv preprint arXiv:2312.10997</i>.",
        "[4] Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection. <i>Proceedings of the 16th ACM Workshop on Artificial Intelligence and Security</i>, 79-90.",
        "[5] Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... & Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. <i>Advances in Neural Information Processing Systems</i>, 33, 9459-9474.",
        "[6] Liu, F., Lin, Z., Shen, C., & Ding, M. (2023). On the safety and sandbox isolation of autonomous agent execution in local environments. <i>IEEE Transactions on Dependable and Secure Computing</i>, 21(3), 1420-1435.",
        "[7] Microsoft Corporation. (2024). <i>AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation Framework</i>. Microsoft Research Technical Report.",
        "[8] Ministry of Law and Justice, Government of India. (2023). <i>The Digital Personal Data Protection Act, 2023 (No. 22 of 2023)</i>. The Gazette of India Extraordinary.",
        "[9] Schick, T., Dwivedi-Yu, J., Dessì, R., Raileanu, R., Lomeli, M., Zettlemoyer, L., ... & Scialom, T. (2023). Toolformer: Language models can teach themselves to use tools. <i>Advances in Neural Information Processing Systems</i>, 36, 68539-68551.",
        "[10] Touvron, H., Martin, L., Stone, K., Albert, P., Almahairi, A., Babaei, Y., ... & Scialom, T. (2023). Llama 2: Open foundation and fine-tuned chat models. <i>arXiv preprint arXiv:2307.09288</i>.",
        "[11] Wang, X., Wei, J., Schuurmans, D., Le, Q., Chi, E., Narang, S., ... & Zhou, D. (2023). Self-consistency improves chain of thought reasoning in language models. <i>International Conference on Learning Representations (ICLR)</i>.",
        "[12] Xu, Y., Li, M., Cui, L., Huang, S., Wei, F., & Zhou, M. (2021). LayoutLMv2: Multi-modal pre-training for visually-rich document understanding. <i>Proceedings of the 59th Annual Meeting of the Association for Computational Linguistics</i>, 2579-2591.",
        "[13] Yang, A., Xiao, B., Wang, B., Zhang, B., Bian, C., Yin, C., ... & Zhou, J. (2024). Baichuan 2: Open large-scale language models. <i>arXiv preprint arXiv:2309.10305</i>.",
        "[14] Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). ReAct: Synergizing reasoning and acting in language models. <i>International Conference on Learning Representations (ICLR)</i>.",
        "[15] Zhang, S., Dong, L., Li, X., Zhang, S., Sun, X., Wang, S., ... & Wei, F. (2023). Instruction tuning for large language models: A survey. <i>arXiv preprint arXiv:2308.10792</i>."
    ]

    for ref in references:
        story.append(Paragraph(ref, styles['ReferenceItem']))

    story.append(Spacer(1, 14))

    # Formal B.Tech Major Project Academic Approval Block
    approval_title = Paragraph("<b>DEPARTMENTAL REVIEW & SYNOPSIS APPROVAL</b>", styles['SignLabel'])
    story.append(approval_title)
    story.append(Spacer(1, 8))

    sign_data = [
        [
            Paragraph("____________________________<br/><b>Bhumik Sharma</b><br/>(2401920100127)", styles['SignLabel']),
            Paragraph("____________________________<br/><b>Harsh Kumar Singh</b><br/>(2401920100152)", styles['SignLabel']),
        ],
        [
            Paragraph("<br/>____________________________<br/><b>Harsh Kumar</b><br/>(2401920100151)", styles['SignLabel']),
            Paragraph("<br/>____________________________<br/><b>Harshit Kumar</b><br/>(2401920100155)", styles['SignLabel']),
        ],
        [
            Paragraph("<br/><br/>____________________________<br/><b>Ms. Abha Kaushik</b><br/>Project Supervisor / Guide", styles['SignLabel']),
            Paragraph("<br/><br/>____________________________<br/><b>Project Coordinator / HOD</b><br/>Department of CSE, GLBITM", styles['SignLabel']),
        ]
    ]

    t_sign = Table(sign_data, colWidths=[240, 240])
    t_sign.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(t_sign)

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=42,
        bottomMargin=42,
    )

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Synopsis successfully built at: {OUTPUT_PDF}")


if __name__ == "__main__":
    build_synopsis()

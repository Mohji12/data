// TODO: replace with API

export const courses = [
  { id: 1, name: 'Critical Care Medicine — Batch 15', duration: '5 months', start: 'January 2026', fee: 35000, enrolled: 127, slug: 'batch-15' },
  { id: 2, name: 'EDIC Part I & II Preparation', duration: '3 months', start: 'February 2026', fee: 18000, enrolled: 89, slug: 'edic-1' },
  { id: 3, name: 'CCM Practical Series Batch 2', duration: '2 months', start: 'March 2026', fee: 15000, enrolled: 64, slug: 'ccm-practical' },
  { id: 4, name: 'Comprehensive Course 1', duration: '6 months', start: 'Rolling', fee: 45000, enrolled: 201, slug: 'comprehensive-1' },
  { id: 5, name: 'Comprehensive Course 2', duration: '6 months', start: 'Rolling', fee: 45000, enrolled: 156, slug: 'comprehensive-2' },
];

/**
 * Public batches (hero pills + navbar buttons).
 * `slugCandidates`: API `/registration/batches` slugs — first match wins per row.
 */
export const marketingBatches = [
  {
    label: 'CCM Batch 2',
    pillTo: '/register/ccm-practical-series',
    slugCandidates: ['ccm-2', 'ccm-practical', 'ccm-batch-2'],
  },
  {
    label: 'CCM Batch 3',
    pillTo: '/register/ccm-practical-series-batch-3',
    slugCandidates: ['ccm-3', 'ccm-practical-series-batch-3', 'ccm-batch-3', 'practical-series-batch-3'],
  },
  {
    label: 'Batch 15',
    pillTo: '/register/batch-15',
    slugCandidates: ['batch-15'],
  },
  {
    label: 'BATCH 9-CC 1',
    pillTo: '/register/comprehensive-course-1',
    slugCandidates: ['batch-9-cc-1', 'comprehensive-course-1', 'comprehensive-1', 'cp-7'],
  },
  {
    label: 'BATCH 9-CC 2',
    pillTo: '/register/comprehensive-course-2',
    slugCandidates: ['batch-9-cc-2', 'comprehensive-course-2', 'comprehensive-2', 'cp-8'],
  },
  {
    label: 'Batch 10 EDIC 1',
    pillTo: '/register/batch-10-edic-1',
    slugCandidates: ['batch-edic-10', 'edic-10', 'batch-10-edic-1', 'edic-1', 'batch-edic-10'],
  },
  {
    label: 'BATCH 16-MCCM',
    pillTo: '/register/batch-16-mccm',
    slugCandidates: ['batch-16-mccm', 'batch-16', 'batch-16-mccm'],
  },
] as const;

/** Hero / navbar batch pills */
export const homeHeroBatchPills = marketingBatches.map((m) => ({ label: m.label, to: m.pillTo }));

export type RegistrationBatchPick<T> = T & { displayTitle: string };

/** Subset of API batches for registration UI, fixed order, marketing labels. */
export function pickRegistrationBatches<T extends { slug: string; title?: string }>(
  batches: T[] | undefined,
): RegistrationBatchPick<T>[] {
  if (!batches?.length) return [];
  const bySlug = new Map(batches.map((b) => [b.slug, b]));
  const out: RegistrationBatchPick<T>[] = [];
  const usedSlugs = new Set<string>();

  // 1. Process marketing batches first to preserve preferred order and labels
  for (const m of marketingBatches) {
    for (const slug of m.slugCandidates) {
      const b = bySlug.get(slug);
      if (b) {
        out.push({ ...b, displayTitle: m.label });
        usedSlugs.add(b.slug);
        break;
      }
    }
  }

  // 2. Append any remaining batches from API that weren't in marketing candidates
  for (const b of batches) {
    if (!usedSlugs.has(b.slug)) {
      // Exclude legacy slugs from being auto-appended (e.g., CP 1-10, old EDIC)
      // These will only show up if explicitly mapped in marketingBatches above.
      const s = b.slug.toLowerCase();
      if (s.startsWith('cp-') || s.startsWith('batch-edic-')) {
        continue;
      }

      out.push({ ...b, displayTitle: b.title || b.slug });
      usedSlugs.add(b.slug);
    }
  }

  return out;
}

/**
 * Always show all matched batches.
 * Preserves the preferred route if it's a known marketing batch, otherwise uses standard /register/slug.
 */
export function buildPublicBatchPills<T extends { slug: string }>(
  batches: T[] | undefined,
): Array<{ label: string; to: string }> {
  const matched = pickRegistrationBatches(batches);

  return matched.map((b) => ({
    label: b.displayTitle,
    to: `/register/${encodeURIComponent(b.slug)}`,
  }));
}

export const sampleMCQ = {
  text: 'A 62-year-old with severe ARDS (P/F 95) on MV: Vt 6ml/kg, PEEP 10, FiO₂ 0.8, plateau 32 cmH₂O, driving pressure 18. SpO₂ 87%. Most important next intervention?',
  options: [
    'Increase PEEP to 16 cmH₂O',
    'Initiate prone positioning ≥16 hours',
    'Inhaled nitric oxide 20 ppm',
    'Increase FiO₂ to 1.0',
  ],
  correct: 1,
  explanation: 'PROSEVA 2013: prone >16h reduced 28-day mortality from 32.8% to 16% in P/F <150 ARDS.',
};

export const testimonials = [
  {
    quote: "Cleared EDIC on my first attempt after three previous failures. Dr. Harish's clinical approach is unlike anything else recorded.",
    name: 'Dr. Priya Menon',
    role: 'DM Critical Care',
    institution: 'AIIMS New Delhi',
  },
  {
    quote: 'Mock tests exactly like the real exam. Questions answered within hours — often by Dr. Harish himself.',
    name: 'Dr. Rahul Sharma',
    role: 'Intensivist',
    institution: 'Apollo Hospitals Hyderabad',
  },
  {
    quote: 'Pre-recorded format let me study during night shifts. Cleared IDCCM written first attempt after Batch 12.',
    name: 'Dr. Ananya Krishnan',
    role: 'Anaesthesiologist',
    institution: 'CMC Vellore',
  },
];

export const mockVideos = [
  { id: '1', title: 'Hemodynamic Monitoring in Septic Shock', duration: '45:30', folder: 'Hemodynamics', watched: true, progress: 100 },
  { id: '2', title: 'Mechanical Ventilation — ARDS Protocol', duration: '62:15', folder: 'Ventilation', watched: true, progress: 100 },
  { id: '3', title: 'Vasopressor Selection & Titration', duration: '38:40', folder: 'Hemodynamics', watched: false, progress: 45 },
  { id: '4', title: 'Renal Replacement Therapy in ICU', duration: '54:20', folder: 'Nephrology', watched: false, progress: 0 },
  { id: '5', title: 'Nutrition in Critical Illness', duration: '41:55', folder: 'General', watched: false, progress: 0 },
  { id: '6', title: 'Sedation & Analgesia Protocols', duration: '33:10', folder: 'General', watched: false, progress: 0 },
];

export const mockQuizzes = [
  { id: '1', title: 'Hemodynamics Assessment', questions: 30, duration: 45, score: 74, status: 'completed' as const, date: '2026-01-15' },
  { id: '2', title: 'Ventilation Strategies', questions: 25, duration: 40, score: null, status: 'pending' as const, date: '2026-01-20' },
  { id: '3', title: 'Sepsis & Shock Management', questions: 30, duration: 45, score: 88, status: 'completed' as const, date: '2026-01-10' },
  { id: '4', title: 'Neuro-Critical Care', questions: 20, duration: 30, score: null, status: 'pending' as const, date: '2026-02-01' },
];

export const mockUsers = [
  { id: '1', name: 'Dr. Priya Menon', email: 'priya@aiims.edu', course: 'Batch 15', status: 'active' as const, joined: '2025-12-01' },
  { id: '2', name: 'Dr. Rahul Sharma', email: 'rahul@apollo.com', course: 'EDIC Prep', status: 'active' as const, joined: '2025-11-15' },
  { id: '3', name: 'Dr. Ananya Krishnan', email: 'ananya@cmc.edu', course: 'Batch 14', status: 'expired' as const, joined: '2025-06-01' },
  { id: '4', name: 'Dr. Vikram Patel', email: 'vikram@kem.edu', course: 'Batch 15', status: 'active' as const, joined: '2025-12-10' },
  { id: '5', name: 'Dr. Sneha Reddy', email: 'sneha@nims.edu', course: 'Comprehensive 1', status: 'active' as const, joined: '2025-10-01' },
];

export const mockPayments = [
  { id: '1', date: '2025-12-01', amount: 35000, course: 'Critical Care — Batch 15', status: 'paid' as const, method: 'UPI' },
  { id: '2', date: '2025-12-15', amount: 18000, course: 'EDIC Preparation', status: 'paid' as const, method: 'Card' },
  { id: '3', date: '2026-01-01', amount: 15000, course: 'CCM Practical Series', status: 'pending' as const, method: 'Bank Transfer' },
];

export const faqData = [
  {
    category: 'Programme',
    items: [
      { q: 'Is This A Completely Online Course? Do I Need To Attend Any Classes At The Institute?', a: 'It is a completely online learning program with self-paced video lectures. All you need is a laptop/ desktop/ tablet/ mobile with good internet connection. Recorded lectures will be available for a period of access duration as predefined. You may study as many times as you wish during that period.' },
      { q: 'Is There Any Workshop Or Hands On Experience?', a: 'Currently, no observer ship or hands-on training is being provided.' },
      { q: 'What is the duration of the Critical Care Medicine course?', a: 'The flagship CCM course runs for 5-6 months depending on the batch, with sessions typically lasting 45-90 minutes each.' },
      { q: 'How long do I have access to the content?', a: 'You get access for the full duration of your enrolled batch plus additional months for revision as specified in your package.' },
    ],
  },
  {
    category: 'Eligibility',
    items: [
      { q: 'Who can enrol in the course?', a: 'The course is designed for MBBS graduates and above — residents, practicing intensivists, anaesthesiologists, physicians, and anyone pursuing critical care fellowships or exams.' },
      { q: 'Is This Course Recognized By MCI Or Similar Organization?', a: 'Medical Council of India does not recognize courses that are offered through online or blended learning platform.' },
      { q: 'Do You Provide Any Placement Assistance?', a: 'No. We do not provide any placement assistance or guarantee.' },
    ],
  },
  {
    category: 'Payments',
    items: [
      { q: 'What payment methods are accepted?', a: 'We accept UPI, credit/debit cards, net banking, and bank transfers.' },
      { q: 'Is there a refund policy?', a: 'Refunds are subject to our terms and conditions. Please contact support for specific details regarding your enrollment.' },
    ],
  },
  {
    category: 'Technical',
    items: [
      { q: 'What device do I need?', a: 'Any modern browser on desktop, tablet, or mobile. We recommend a stable internet connection for smooth video playback.' },
      { q: 'Can I download videos for offline viewing?', a: 'Currently, videos are streaming-only to protect intellectual property. You can watch them as many times as you like while online.' },
    ],
  },
];

export const galleryImages = [
  '/gallery/Picture1.jpg',
  '/gallery/Picture2.jpg',
  '/gallery/Picture3.jpg',
  '/gallery/Picture4.jpg',
  '/gallery/Picture5.jpg',
  '/gallery/Picture6.jpg',
  '/gallery/Picture7.jpg',
  '/gallery/Picture8.jpg',
  '/gallery/Picture9.jpg',
  '/gallery/Picture10.jpg',
  '/gallery/Picture11.jpg',
  '/gallery/Picture12.jpg',
  '/gallery/Picture13.jpg',
  '/gallery/Picture14.jpg',
  '/gallery/Picture15.jpg',
  '/gallery/Picture16.jpg',
  '/gallery/Picture17.jpg',
  '/gallery/Picture18.jpg',
  '/gallery/Picture19.jpg',
  '/gallery/Picture20.jpg',
  '/gallery/Picture21.jpg',
  '/gallery/Picture22.jpg',
  '/gallery/Picture23.jpg',
  '/gallery/Picture24.jpg',
  '/gallery/Picture25.jpg',
  '/gallery/Picture26.jpg',
  '/gallery/Picture27.jpg',
  '/gallery/Picture28.jpg',
  '/gallery/Picture29.jpg',
  '/gallery/Picture30.jpg',
];

export const features = [
  { icon: 'MonitorCheck', title: 'Bedside-First Curriculum', desc: 'Every topic is taught from the ICU bedside, not from textbooks. Real cases, real protocols, real decision-making.' },
  { icon: 'Brain', title: 'EDIC-Aligned Content', desc: 'Structured to mirror the European Diploma syllabus with targeted preparation for Parts I and II.' },
  { icon: 'ClipboardCheck', title: 'MCQ Bank & Mock Tests', desc: '3000+ clinical MCQs with detailed explanations. Timed mock exams that simulate the real testing environment.' },
  { icon: 'Users', title: 'Peer Community', desc: 'Join 6000+ doctors in focused discussion groups. Case presentations, journal clubs, and peer learning.' },
  { icon: 'Shield', title: 'Evidence-Based Approach', desc: 'Every teaching point is backed by landmark trials and current guidelines. No opinion-based medicine.' },
  { icon: 'Award', title: '90% EDIC Pass Rate', desc: '15 batches completed. 6000+ doctors trained. The highest EDIC pass rate from any Indian programme.' },
];

/** Awards, honours & scholarships — chronological (newest last in section flow; page renders in this order). */
export type AwardEntry = { year: string; detail: string };

export const awards: AwardEntry[] = [
  {
    year: '2010',
    detail:
      'Got “Travelling Fellowship” to participate and to present a paper at the National Conference (ISACON-2010) at Lucknow.',
  },
  {
    year: '2010',
    detail:
      'First Prize for “Best Paper Presentation” conducted by ISA, Nagpur division.',
  },
  {
    year: '2015',
    detail:
      'Finished DM in Critical Care Medicine with the honour of India’s first MCI-recognised DM in Critical Care Medicine from the prestigious institute, continued at Tata Memorial Hospital.',
  },
  {
    year: '2016',
    detail:
      'Award from the Indian Society of Critical Care Medicine (ISCCM) for presenting the paper “Prospective study to determine the incidence and risk factors associated with delirium in cancer patients in ICU” at the National Conference in Agra.',
  },
  {
    year: '2016',
    detail:
      '“Young Intensivist” travelling grant to participate in the National Conference in Agra.',
  },
  {
    year: '2018',
    detail: 'Identified as an “excellent speaker” by ISCCM Vizag.',
  },
  {
    year: '2019',
    detail: 'Esteemed reviewer, Indian Journal of Respiratory Care.',
  },
  {
    year: '2019',
    detail: 'Editorial board member, Indian Journal of Respiratory Care.',
  },
  {
    year: '2022',
    detail: 'Editor-in-Chief, Indian Journal of Respiratory Care (IJRC).',
  },
  {
    year: '2023',
    detail: 'President, Indian Association of Respiratory Care (IARC).',
  },
  {
    year: '2023',
    detail:
      'Received honorary Fellowship from the Indian Association of Respiratory Care (FIARC) from the Honourable Minister for Health and Family Welfare, Government of Karnataka.',
  },
  {
    year: '2024',
    detail: 'Promising Intensivist 2024 award from TIMES NETWORK.',
  },
  {
    year: '—',
    detail: 'Esteemed member of the Panel of Examiners to examine PhD theses from the University.',
  },
  {
    year: '2025',
    detail: '“Health Care Excellence Award 2025” from The Academic Insights.',
  },
];

/** Dr. Harish — faculty credentials for /faculty page */
export type FacultyPresentation = { year: string; detail: string };

/** Professional society memberships — /membership page (ESICM = European Society of Intensive Care Medicine). */
export const professionalSocietyMemberships: string[] = [
  'Karnataka Medical Council (KMC)',
  'Indian Society of Critical Care Medicine (ISCCM)',
  'European Society of Intensive Care Medicine (ESICM)',
  'Indian Society of Neuro-anesthesia and Critical Care (ISNAC)',
  'Indian Society of Anesthesia (ISA)',
  'American College of Chest Physicians (ACCP)',
  'Indian Society for Parenteral and Enteral Nutrition (ISPEN)',
];

export const facultyProfile = {
  displayName: 'Dr Harish Mallapura Maheshwarappa',
  degrees:
    'MBBS, MD, DNB, IDCCM, DM (Critical Care Medicine), EDIC (Dublin), Fellowship in Infectious Diseases, FIARC, MBA.',
  titles: [
    'Intensive Care Physician and Infectious Diseases Specialist',
    'Director — Institute of Critical Care Medicine',
    'Kauvery Hospitals, Bengaluru',
  ],
  highlights: [
    'More than 16 years of experience',
    'India’s first Medical Council of India (MCI) recognised DM in Critical Care Medicine',
    'European Diploma in Intensive Care Medicine (EDIC) from Dublin',
    'More than fifty publications in international and national indexed journals',
    'Authored more than thirty chapters in various academic books',
    'Received “Young Intensivist” award from the Indian Society of Critical Care Medicine',
    'Recognised as “Promising Intensivist 2024” from Times Network',
    'Received “Health Care Excellence Award 2025” from The Academic Insights',
    'President — Indian Association of Respiratory Care (IARC)',
    'Editor-in-Chief Emeritus — Indian Journal of Respiratory Care (IJRC)',
    'Editorial board member — ISCCM Newsletter',
    'Esteemed reviewer — Indian Journal of Critical Care Medicine (IJCCM)',
    'Member of guideline committee — Indian Society of Critical Care Medicine (ISCCM)',
    'Recognised teacher and examiner for DrNB and IDCCM/IFCCM trainees in critical care medicine',
    'Founder and course director — Master Classes in Critical Care Medicine (online learning platform)',
    'Researcher; national and international speaker at academic conferences',
    'Organised many conferences and workshops in critical care medicine',
    'MBA in Hospital Management — special interest in healthcare administration',
  ],
  expertise: [
    'Treating complex infectious diseases',
    'Managing multidrug-resistant organisms',
    'Protocolized management of critically ill patients',
    'Advanced hemodynamic monitoring',
    'End-of-life care principles',
    'Adult HFOV and prone ventilation',
    'Trauma critical care',
    'Delirium in ICU patients',
    'Nutrition in the critically ill',
    'Oncological emergencies',
    'Isolation and infection control policies',
    'Antibiotic stewardship',
    'Intrahospital transport of critically ill patients',
    'Organization of rounds, seminars and teaching sessions',
    'Clinical research, medical ethics, statistics, epidemiology and administration',
  ],
  memberships: professionalSocietyMemberships,
  training: [
    'EPIC — Echo Protocol in Intensive Care and 2D echo workshop (certified by Global Health Alliance, UK, and University of Leeds) — 2017',
    'Basic Life Support (BLS)',
    'Advanced Cardiac Life Support (ACLS)',
  ],
  presentations: [
    {
      year: '2010',
      detail:
        'Presented dissertation study “Comparative study of high concentration vs incremental concentration of sevoflurane as induction agent in paediatric patients” at ISACON-2010, Lucknow.',
    },
    {
      year: '2010',
      detail:
        'Poster: “Alternative technique of intubation in Pierre Robin syndrome” — selected for the Isha Naraini Award at ISACON-2010, Lucknow.',
    },
    {
      year: '2012',
      detail:
        'Poster: “Comparison of suicidal hanging between Indian and western data” — National Conference of Critical Care Medicine, Pune.',
    },
    {
      year: '2013',
      detail:
        'Poster: “Complete heart block in a case of aortic root abscess” — National Conference of Critical Care Medicine, Kolkata.',
    },
    {
      year: '2015',
      detail:
        'Poster: “Audit on intrahospital transport of ICU patients in a tertiary care cancer hospital” — National Conference of Critical Care Medicine, Bengaluru.',
    },
    {
      year: '2016',
      detail:
        'Paper: “Prospective study to determine the incidence and risk factors associated with delirium in cancer patients in ICU” — National Conference, Agra.',
    },
    {
      year: '2016',
      detail:
        'Poster: same delirium study — Platinum Jubilee Conference, Tata Memorial Hospital, Mumbai.',
    },
    {
      year: '2016',
      detail:
        'Paper: delirium in Indian cancer ICU patients — International conference (ESICM), Milan, Italy.',
    },
    {
      year: '2019',
      detail:
        'Paper: “Observational study on the clinical utility of intravenous fosfomycin in an Indian tertiary care ICU” — SG-ANZICS, Singapore.',
    },
    {
      year: '2020',
      detail:
        'Virtual presentation: “Validation of an isothermal amplification platform for microbial identification and antimicrobial resistance detection in blood: a prospective study” — European Congress of Clinical Microbiology & Infectious Diseases (ECCMID).',
    },
  ] as FacultyPresentation[],
};

/** Peer-reviewed papers & reviews (indexed journals) — /publications */
export const peerReviewedPublications: string[] = [
  'Complications and benefits of intrahospital transport of adult intensive care unit patients. Indian J Crit Care Med 2016;20:448-52. Prospective observational study.',
  'Agreement between inferior vena cava diameter measurements by subxiphoid versus transhepatic views. Indian J Crit Care Med 2015;19:719-22. Prospective observational study.',
  'Complications of tracheal intubation in critically ill pediatric cancer patients. Indian J Crit Care Med 2016;20:409-11. Prospective observational study.',
  'Harish MM, Siddiqui SS, Prabu NR, Chaudhari HK, Divatia JV, Kulkarni AP. Benefits of and untoward events during intrahospital transport of pediatric intensive care unit patients. Indian J Crit Care Med.',
  'Aortic root abscess with complete heart block in a patient with acute lymphoblastic leukaemia (Harish MM et al.). J Med Sci Clin Res 2017;5(8).',
  'Chemotherapy induced cardiotoxicity—a case-based review. Int J Med Sci Clin Invent 2017;4(11):3299-3303.',
  'Harish MM, Ruhatiya RS. Influenza H1N1 infection in immunocompromised host: A concise review. Lung India 2019;36:330-6.',
  'Kothekar AT, Divatia JV, Myatra SN, et al. Clinical pharmacokinetics of 3-hour extended infusion of meropenem in adult patients with severe sepsis and septic shock: implications for empirical therapy against Gram-negative bacteria. Ann Intensive Care 2020;10:4.',
  'Ruhatiya RS, Adukia SA, Manjunath RB, Maheshwarappa HM. Current status and recommendations in multimodal neuromonitoring. Indian J Crit Care Med 2020;24(5):353-60.',
  'Adukia SA, Ruhatiya RS, Maheshwarappa HM, Manjunath RB, Jain GN. Extrapulmonary features of COVID-19: A concise review. Indian J Crit Care Med 2020;24(7):575-80.',
  'Harish MM, Ramya BM. Challenges with present symptom control and risk reduction of future exacerbations in asthma: Indian patients’ perspectives. Indian J Respir Care 2020;9:129-30.',
  'Majumder S, Maheshwarappa H. Immune response in the wake of COVID-19 infection—a two-edged sword. World J Pharm Pharm Sci 2020;9. DOI: 10.20959/wjpps20207-16580.',
  'Harish Mallapura Maheshwarappa, Ramya BM, Ruhatiya RS, Adukia S, Sudhindra P, Hegde S, Ummi Salma. A concise review on newer modes of ventilation in acute respiratory distress syndrome. Int J Med Health Sci 2020;10(6):951-54.',
  'Validation of an isothermal amplification platform for microbial identification and antimicrobial resistance detection in blood: A prospective study. Indian J Crit Care Med 2021;25(3):299-304.',
  'Use of handheld ultrasound device with artificial intelligence for evaluation of the cardiorespiratory system in COVID-19. Indian J Crit Care Med 2021;25(5):524-27.',
  'Maheshwarappa HM, Machanalli G, Thilakchand KR, Tejaswini DDS. The story of an abscess: A case of Mycobacterium abscessus infection in an immunocompetent patient. Indian J Crit Care Med 2022;26(4):533-34.',
  'Chaudhuri S, Maheshwarappa HM. Ultrasound-based weaning indices: The need of the hour? Indian J Respir Care 2022;11(3):195-99.',
  'Raman RA, Maheshwarappa HM. Managing acute exacerbation of chronic obstructive pulmonary disease: What’s new? Indian J Respir Care 2022;11(4):287-90.',
  'Maheshwarappa HM, Sidharth R. Quality and errors in the intensive care unit. Indian J Respir Care 2022;11(2):87-94.',
  'Relevance of troponin I elevation among individuals with hypertensive emergency. Indian J Crit Care Med 2022;26(7):767-69.',
  'Rai AV, Harish M. A rare case of primary pyogenic ventriculitis in a patient with community-acquired meningitis. Indian J Crit Care Med 2022;26(7):874-76.',
];

/** Book & textbook chapters */
export const bookChaptersPublished: string[] = [
  'Chapter: “Current utility of ETCO₂ in ICU” — ISCCM book (2017).',
  'Chapter: “Treatment of atrial fibrillation in ICU” — ISCCM (2018).',
  'Chapter: “Newer methods in sterilization and disinfection in ICU” — ISCCM (2018).',
  'Chapter on hyponatremia — Case Based Review in Critical Care Medicine: A Comprehensive Preparatory Book for the Examinee (ISCCM).',
  'Chapter: adjunctive therapies in acute myocardial infarction — Asia Pacific / evidence-based core topics volume (ISCCM, 2019).',
  'Chapter: “Vasopressors in critically ill patients” — THEMATAICS (Tata Memorial Hospital).',
  'Chapter: “Critical care in the peri-operative period—need, indications, infrastructure and staffing” — Perioperative Critical Care textbook.',
  'Chapter: “Perioperative hemodynamic monitoring” — Perioperative Critical Care Medicine.',
  'Chapter: “Pro–brain natriuretic peptide–guided therapy in heart failure” — Critical Care Update 2020 (ISCCM).',
  'Chapter: MCQs in “Hemodynamic monitoring” — Critical Care Medicine MCQs Practical Book 2019 (ISCCM).',
  'Chapter: “Technology of non-invasive ventilation” — Updates on NIV textbook.',
  'Chapter: “Delirium in ICU: Detection, evaluation and prevention” — Bench to Bedside: Critical Care Medicine textbook.',
  'Chapter: “Use of echo in assessing fluid responsiveness” — Critical Care Update Book 2023.',
  'Chapter: “Recent advances for immunotherapies against infectious diseases” — Contemporary Topics in Critical Care Medicine.',
  'Chapter: “Hemodynamic coherence” — Textbook of Critical Care Medicine.',
  'Chapter: “Infective endocarditis” — Decision Making in Critical Care Medicine.',
  'Chapter: “Acute myocarditis” — Decision Making in Critical Care Medicine.',
  'Chapter: “Management of patients with valvular heart disease” — Decision Making in Critical Care Medicine.',
  'Chapter: “Vasoactive drugs and splanchnic circulation” — Applied Physiology and Pharmacology.',
  'Chapter: “Lymph circulation” — Applied Physiology and Pharmacology.',
  'Chapter: “Hemodynamic coherence” — Applied Physiology and Pharmacology.',
  'Chapter: “Advanced modes of mechanical ventilation” — Respiratory Critical Care Medicine.',
  'Chapter: “Essentials of mechanical ventilation” — Respiratory Critical Care Medicine.',
  'Chapter: “State-of-the-art review—ACS and cardiogenic shock” — ISCCM Critical Care Update.',
  'Chapter: “Fluid management in ECMO” — ECMO Handbook.',
  'Chapter: “Endocrine emergencies” — ICU Protocols (2024).',
];

/** Manuscripts and trials in progress */
export const researchInProgress: string[] = [
  'Prospective study to determine the incidence and risk factors associated with ICU delirium in Indian cancer patients — data analysis in progress (prospective observational study).',
  'A prospective pharmacokinetics and dose optimisation study of extended infusion of meropenem in adult critically ill cancer patients — manuscript ready for submission.',
  'Comparative study of high concentration versus incremental concentration of sevoflurane as induction agent in paediatric patients — manuscript ready for submission (prospective observational study).',
  'Prospective observational study on the clinical utility of high-flow nasal cannula in an Indian tertiary care centre.',
  'Hemadsorption (CytoSorb®) in management of cytokine storm — implications in the COVID-19 pandemic.',
  'Phase 3, prospective, randomised, open-label, comparative clinical study of ulinastatin plus standard-of-care versus standard-of-care in acute respiratory distress syndrome in hospitalised COVID-19 patients.',
  'Prevalence, risk factors and outcome of candida infection in a tertiary care centre in the background of the COVID-19 pandemic: single-centre retrospective analysis.',
  'Prospective, multi-centre, active post-marketing surveillance of liposomal amphotericin B (Amphonex®, Bharat Serums and Vaccines Ltd.) in patients with invasive fungal infection who are refractory to or intolerant of conventional amphotericin B therapy in real-world practice (AMBeR).',
];

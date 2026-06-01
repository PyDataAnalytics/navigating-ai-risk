"""Authored disambiguation lines for Pass B.

Each entry is keyed by (source_name, similar_sibling_name) → disambiguation text.

The text tells the matcher: "pick SOURCE when X, pick SIBLING when Y" — both
sides, balanced. Existing one-sided does_not_apply_when references are NOT
sufficient.

Authoring constraints:
- One sentence, ~15-25 words.
- Both sides explicit. Format: "Source for X; sibling for Y."
- No category jargon — the matcher LLM has the full definitions in context.
- Pull from each entry's applies_when, not invented framings.
"""

DISAMBIGUATIONS: dict[tuple[str, str], str] = {
    # ────────────────────────────────────────────────────────────────────────
    # Category 1 — Technical & Reliability Risks (99 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Hallucinations",
        "Fabricated citations or sources",
    ): "Hallucinations for fabricated facts in general output; Fabricated citations for the specific case of invented papers, cases, or URLs.",
    (
        "Hallucinations",
        "Incorrect reasoning",
    ): "Hallucinations when the asserted facts are wrong; Incorrect reasoning when the facts are right but the logic connecting them is broken.",
    (
        "Hallucinations",
        "Misunderstanding context or intent",
    ): "Hallucinations when output is factually false; Misunderstanding when output is factually fine but answers the wrong question.",
    (
        "Fabricated citations or sources",
        "Hallucinations",
    ): "Fabricated citations for invented references, papers, or URLs specifically; Hallucinations for invented facts in the body of the output.",
    (
        "Fabricated citations or sources",
        "Automated plagiarism",
    ): "Fabricated citations when sources are made up; Automated plagiarism when real sources are copied without attribution.",
    (
        "Fabricated citations or sources",
        "Fake scientific papers by AI",
    ): "Fabricated citations when an LLM cites nonexistent papers in user output; Fake scientific papers when AI produces fraudulent published research.",
    (
        "Fabricated citations or sources",
        "Academic dishonesty with AI",
    ): "Fabricated citations for the LLM-side fabrication mechanism; Academic dishonesty for the student-side use of AI to cheat.",
    (
        "Incorrect reasoning",
        "Arithmetic and logical errors",
    ): "Incorrect reasoning for inferential or causal errors broadly; Arithmetic and logical errors when failure is specifically in numerical or formal-logic operators.",
    (
        "Incorrect reasoning",
        "Hallucinations",
    ): "Incorrect reasoning when premises are correct but conclusion doesn't follow; Hallucinations when one of the premises is itself fabricated.",
    (
        "Incorrect reasoning",
        "Misunderstanding context or intent",
    ): "Incorrect reasoning when the LLM addresses the right question with broken logic; Misunderstanding when the LLM applies fine logic to the wrong question.",
    (
        "Incorrect reasoning",
        "Cascading system failures",
    ): "Incorrect reasoning for a single model's faulty logic; Cascading failures when a reasoning error propagates through multiple downstream AI components.",
    (
        "Incorrect reasoning",
        "Deceptive alignment",
    ): "Incorrect reasoning when the model is honestly mistaken; Deceptive alignment when the model produces wrong output strategically to avoid oversight.",
    (
        "Arithmetic and logical errors",
        "Incorrect reasoning",
    ): "Arithmetic and logical errors for numerical computation or formal-logic mistakes; Incorrect reasoning for broader inferential or causal errors.",
    (
        "Arithmetic and logical errors",
        "Hallucinations",
    ): "Arithmetic and logical errors when computations or formal operators fail; Hallucinations when factual claims are made up.",
    (
        "Arithmetic and logical errors",
        "Brittleness outside training distribution",
    ): "Arithmetic and logical errors for the symbolic-operator failure mode; Brittleness when an ML model fails on inputs outside its training distribution.",
    (
        "Misunderstanding context or intent",
        "Hallucinations",
    ): "Misunderstanding when the LLM answers the wrong question correctly; Hallucinations when the LLM answers any question with invented facts.",
    (
        "Misunderstanding context or intent",
        "Incorrect reasoning",
    ): "Misunderstanding when the LLM misreads what was asked; Incorrect reasoning when the LLM reads the request correctly but reasons badly from it.",
    (
        "Misunderstanding context or intent",
        "Specification gaming",
    ): "Misunderstanding when the model accidentally misreads intent; Specification gaming when the model deliberately exploits a literal-but-wrong reading.",
    (
        "Misunderstanding context or intent",
        "Goal misgeneralization",
    ): "Misunderstanding for one-shot prompt-level intent failures; Goal misgeneralization for systematic divergence between trained goal and deployment intent.",
    (
        "Misunderstanding context or intent",
        "Objective misspecification",
    ): "Misunderstanding for run-time intent confusion; Objective misspecification when the original training objective itself didn't capture operator intent.",
    (
        "Overfitting and underfitting",
        "Brittleness outside training distribution",
    ): "Overfitting/underfitting for failure modes diagnosed during training; Brittleness for the deployment-time symptom of failing on out-of-distribution inputs.",
    (
        "Overfitting and underfitting",
        "Distribution shift failures",
    ): "Overfitting/underfitting when the training process itself was flawed; Distribution shift when training was fine but the deployed data has drifted from it.",
    (
        "Overfitting and underfitting",
        "Catastrophic forgetting",
    ): "Overfitting/underfitting for single-task generalization failures; Catastrophic forgetting when sequential training on new tasks erases previously learned ones.",
    (
        "Brittleness outside training distribution",
        "Distribution shift failures",
    ): "Brittleness for failure on any input outside training distribution; Distribution shift specifically for gradual drift of the real-world data distribution over time.",
    (
        "Brittleness outside training distribution",
        "Overfitting and underfitting",
    ): "Brittleness for the deployment symptom on OOD inputs; Overfitting/underfitting for the underlying training-process cause.",
    (
        "Brittleness outside training distribution",
        "Adversarial examples",
    ): "Brittleness for natural OOD inputs that fail unintentionally; Adversarial examples for inputs deliberately crafted to fail.",
    (
        "Brittleness outside training distribution",
        "Failure under adversarial inputs",
    ): "Brittleness for unintentional failures on natural OOD inputs; Failure under adversarial inputs for failures on attacker-crafted inputs.",
    (
        "Failure under adversarial inputs",
        "Adversarial examples",
    ): "Failure under adversarial inputs as the general failure category; Adversarial examples specifically for imperceptibly-perturbed inputs that fool classifiers.",
    (
        "Failure under adversarial inputs",
        "Prompt injection attacks",
    ): "Failure under adversarial inputs for classical ML attack inputs; Prompt injection for LLM-specific attacks via text in context, retrieval, or tool output.",
    (
        "Failure under adversarial inputs",
        "Brittleness outside training distribution",
    ): "Failure under adversarial inputs for attacker-crafted inputs; Brittleness for unintentional failures on natural OOD inputs.",
    (
        "Failure under adversarial inputs",
        "Jailbreaks",
    ): "Failure under adversarial inputs for inputs that produce wrong outputs; Jailbreaks for inputs that bypass safety training to elicit refused content.",
    (
        "Prompt injection attacks",
        "Jailbreaks",
    ): "Prompt injection when attacker text reaches LLM context via tools, retrieval, or user data; Jailbreaks when the user directly bypasses safety training.",
    (
        "Prompt injection attacks",
        "Failure under adversarial inputs",
    ): "Prompt injection for LLM context-poisoning attacks specifically; Failure under adversarial inputs for the broader ML adversarial-input category.",
    (
        "Jailbreaks",
        "Prompt injection attacks",
    ): "Jailbreaks when users bypass safety training directly; Prompt injection when external content (retrieved data, tool output) hijacks the model.",
    (
        "Jailbreaks",
        "Failure under adversarial inputs",
    ): "Jailbreaks for safety-bypass to elicit refused content; Failure under adversarial inputs for inputs that produce incorrect classifications.",
    (
        "Adversarial examples",
        "Failure under adversarial inputs",
    ): "Adversarial examples specifically for imperceptibly-perturbed inputs fooling classifiers; Failure under adversarial inputs as the broader category.",
    (
        "Adversarial examples",
        "Brittleness outside training distribution",
    ): "Adversarial examples for deliberately crafted perturbations; Brittleness for unintentional failure on natural OOD inputs.",
    (
        "Adversarial examples",
        "Prompt injection attacks",
    ): "Adversarial examples for classical ML perturbation attacks; Prompt injection for LLM context-text attacks.",
    (
        "Adversarial examples",
        "Data poisoning",
    ): "Adversarial examples for inference-time crafted inputs; Data poisoning for training-time corruption that creates backdoors.",
    (
        "Data poisoning",
        "Adversarial examples",
    ): "Data poisoning for training-time data corruption creating backdoors; Adversarial examples for inference-time crafted inputs against a clean model.",
    (
        "Distribution shift failures",
        "Silent degradation over time",
    ): "Distribution shift specifically when the data distribution drifts; Silent degradation as the broader pattern of unnoticed decline including non-distribution causes.",
    (
        "Distribution shift failures",
        "Brittleness outside training distribution",
    ): "Distribution shift for gradual drift of the real-world data over time; Brittleness for any failure on inputs outside training distribution.",
    (
        "Distribution shift failures",
        "Poor monitoring or observability",
    ): "Distribution shift as the failure mechanism; Poor monitoring as the operational gap that lets distribution shift go undetected.",
    (
        "Distribution shift failures",
        "Dependency on external APIs and models",
    ): "Distribution shift when your input data drifts; Dependency on external APIs when a vendor's model behavior changes underneath you.",
    (
        "Catastrophic forgetting",
        "Silent degradation over time",
    ): "Catastrophic forgetting specifically when sequential training erases prior knowledge; Silent degradation for any unnoticed production performance decline.",
    (
        "Catastrophic forgetting",
        "Distribution shift failures",
    ): "Catastrophic forgetting when retraining causes capability loss; Distribution shift when input data drifts away from training without retraining.",
    (
        "Catastrophic forgetting",
        "Overfitting and underfitting",
    ): "Catastrophic forgetting for sequential-task interference; Overfitting/underfitting for single-task generalization failures.",
    (
        "Catastrophic forgetting",
        "Unexpected emergent behaviors",
    ): "Catastrophic forgetting for loss of trained capabilities after retraining; Unexpected emergent behaviors for new capabilities appearing in larger models.",
    (
        "Unexpected emergent behaviors",
        "Unpredictable outputs",
    ): "Unexpected emergent behaviors for new capabilities appearing with scale; Unpredictable outputs for output variability on identical inputs.",
    (
        "Unexpected emergent behaviors",
        "Goal misgeneralization",
    ): "Unexpected emergent behaviors for new capabilities not seen in smaller models; Goal misgeneralization for coherently pursuing the wrong goal in new contexts.",
    (
        "Objective misspecification",
        "Reward hacking",
    ): "Objective misspecification when the formal objective doesn't capture operator intent; Reward hacking when the RL agent exploits the reward function as written.",
    (
        "Objective misspecification",
        "Proxy gaming",
    ): "Objective misspecification for any specification failure; Proxy gaming specifically when the gap is between a proxy metric and the true underlying objective.",
    (
        "Objective misspecification",
        "Goal misgeneralization",
    ): "Objective misspecification when the specification was wrong from the start; Goal misgeneralization when the spec was fine but the trained goal diverges out of distribution.",
    (
        "Objective misspecification",
        "Specification gaming",
    ): "Objective misspecification for the specification's incorrectness; Specification gaming for the model's behavior of exploiting that incorrectness literally.",
    (
        "Objective misspecification",
        "Inner misalignment",
    ): "Objective misspecification when the training objective itself is wrong; Inner misalignment when the training objective is fine but the model internally pursues something else.",
    (
        "Reward hacking",
        "Specification gaming",
    ): "Reward hacking specifically for RL reward-function exploits; Specification gaming for the broader pattern of satisfying literal spec while violating intent.",
    (
        "Reward hacking",
        "Proxy gaming",
    ): "Reward hacking for RL reward exploits; Proxy gaming specifically when the gap is between a proxy and the underlying objective the proxy was meant to track.",
    (
        "Reward hacking",
        "Wireheading",
    ): "Reward hacking when the agent exploits the reward function indirectly via the environment; Wireheading when the agent directly modifies or seizes its own reward signal.",
    (
        "Reward hacking",
        "Objective misspecification",
    ): "Reward hacking for the behavior of exploiting reward; Objective misspecification for the upstream cause of the reward function being wrong.",
    (
        "Reward hacking",
        "Goal misgeneralization",
    ): "Reward hacking when the agent exploits reward at training; Goal misgeneralization when a model pursues a coherent but wrong goal at deployment.",
    (
        "Wireheading",
        "Reward hacking",
    ): "Wireheading when the agent directly modifies or seizes its own reward signal; Reward hacking when the agent exploits the reward function via the environment.",
    (
        "Wireheading",
        "Specification gaming",
    ): "Wireheading for direct reward-signal seizure; Specification gaming for satisfying the literal task spec in unintended ways.",
    (
        "Wireheading",
        "Deceptive alignment",
    ): "Wireheading for direct manipulation of the reward mechanism; Deceptive alignment for behavioral deception during training to pursue different goals at deployment.",
    (
        "Proxy gaming",
        "Reward hacking",
    ): "Proxy gaming specifically when the gap is between a proxy metric and the true objective; Reward hacking for RL reward-function exploits broadly.",
    (
        "Proxy gaming",
        "Objective misspecification",
    ): "Proxy gaming for the optimizer's exploitation behavior; Objective misspecification for the upstream cause that the specified objective was a poor proxy.",
    (
        "Proxy gaming",
        "Specification gaming",
    ): "Proxy gaming specifically about proxy-vs-true-objective gaps; Specification gaming for the broader literal-spec-vs-intent gap.",
    (
        "Goal misgeneralization",
        "Inner misalignment",
    ): "Goal misgeneralization for deployment-time divergence on slightly different conditions; Inner misalignment for the underlying mesa-optimization mechanism that produces it.",
    (
        "Goal misgeneralization",
        "Deceptive alignment",
    ): "Goal misgeneralization when the model honestly pursues a wrong-but-trained goal; Deceptive alignment when the model strategically conceals its true goal until deployment.",
    (
        "Goal misgeneralization",
        "Objective misspecification",
    ): "Goal misgeneralization when the trained goal diverges out of distribution; Objective misspecification when the training objective itself was wrong from the start.",
    (
        "Goal misgeneralization",
        "Specification gaming",
    ): "Goal misgeneralization for emergent goal-divergence at deployment; Specification gaming for the model deliberately satisfying spec while violating intent.",
    (
        "Goal misgeneralization",
        "Unexpected emergent behaviors",
    ): "Goal misgeneralization for coherent pursuit of a wrong goal; Unexpected emergent behaviors for new capabilities appearing with model scale.",
    (
        "Goal misgeneralization",
        "Misaligned superintelligence",
    ): "Goal misgeneralization as a present empirical phenomenon in capable systems; Misaligned superintelligence as the long-term framing of the same dynamic at frontier scale.",
    (
        "Instrumental convergence",
        "Deceptive alignment",
    ): "Instrumental convergence for the theoretical claim that capable agents develop convergent subgoals; Deceptive alignment for the specific behavioral case of strategic alignment-faking.",
    (
        "Deceptive alignment",
        "Goal misgeneralization",
    ): "Deceptive alignment when the model strategically conceals its true goal; Goal misgeneralization when the model honestly pursues a trained-but-wrong goal.",
    (
        "Deceptive alignment",
        "Inner misalignment",
    ): "Deceptive alignment for the specific deceptive behavior; Inner misalignment for the broader mesa-optimization gap that may produce it.",
    (
        "Deceptive alignment",
        "Instrumental convergence",
    ): "Deceptive alignment for the concrete behavior of strategic alignment-faking; Instrumental convergence for the underlying theory of convergent subgoals.",
    (
        "Deceptive alignment",
        "Power-seeking AI behavior",
    ): "Deceptive alignment for the deception itself; Power-seeking for the substantive goal-pursuit (resources, influence) that deception may enable.",
    (
        "Deceptive alignment",
        "Misaligned superintelligence",
    ): "Deceptive alignment as a present-day capability concern with empirical evals; Misaligned superintelligence as the long-term framing at frontier scale.",
    (
        "Inner misalignment",
        "Goal misgeneralization",
    ): "Inner misalignment for the mesa-optimization mechanism where internal objective diverges from training objective; Goal misgeneralization for the deployment-time symptom.",
    (
        "Inner misalignment",
        "Deceptive alignment",
    ): "Inner misalignment for the broader gap between trained and effectively-pursued objective; Deceptive alignment for the specific case where that gap is strategically concealed.",
    (
        "Inner misalignment",
        "Objective misspecification",
    ): "Inner misalignment when the training objective is fine but the model effectively pursues something else; Objective misspecification when the training objective itself fails to capture intent.",
    (
        "Inner misalignment",
        "Reward hacking",
    ): "Inner misalignment for the mesa-optimization mechanism; Reward hacking for the surface behavior of exploiting reward.",
    (
        "Inner misalignment",
        "Misaligned superintelligence",
    ): "Inner misalignment as a present empirical alignment concern; Misaligned superintelligence as the long-term framing of the same dynamic.",
    (
        "Specification gaming",
        "Reward hacking",
    ): "Specification gaming for the broad pattern of satisfying literal spec while violating intent; Reward hacking specifically for RL agents exploiting reward functions.",
    (
        "Specification gaming",
        "Proxy gaming",
    ): "Specification gaming for the broad literal-spec-vs-intent gap; Proxy gaming specifically when the gap is between a proxy metric and the true objective.",
    (
        "Specification gaming",
        "Objective misspecification",
    ): "Specification gaming for the model's exploitative behavior; Objective misspecification for the upstream cause that the spec was incorrect.",
    (
        "Specification gaming",
        "Goal misgeneralization",
    ): "Specification gaming for deliberate exploitation of literal spec; Goal misgeneralization for emergent goal-divergence at deployment.",
    (
        "Unpredictable outputs",
        "Non-determinism in LLMs",
    ): "Unpredictable outputs for any meaningful output variability; Non-determinism specifically for the floating-point and batch-composition causes even at temperature 0.",
    (
        "Unpredictable outputs",
        "Silent degradation over time",
    ): "Unpredictable outputs for run-to-run variability now; Silent degradation for gradual performance decline over time.",
    (
        "Unpredictable outputs",
        "Hallucinations",
    ): "Unpredictable outputs for output variability across runs; Hallucinations for outputs being factually wrong.",
    (
        "Unpredictable outputs",
        "Poor monitoring or observability",
    ): "Unpredictable outputs as the symptom in production; Poor monitoring as the operational gap that prevents detecting it.",
    (
        "Non-determinism in LLMs",
        "Unpredictable outputs",
    ): "Non-determinism specifically for the floating-point and batch-composition causes; Unpredictable outputs for any meaningful output variability regardless of cause.",
    (
        "Non-determinism in LLMs",
        "Poor monitoring or observability",
    ): "Non-determinism for the underlying mechanism that makes outputs vary; Poor monitoring for the broader gap in detecting AI system problems.",
    (
        "Cascading system failures",
        "Dependency on external APIs and models",
    ): "Cascading system failures when failure propagates across components; Dependency on external APIs when the propagation source is specifically a third-party vendor change.",
    (
        "Silent degradation over time",
        "Distribution shift failures",
    ): "Silent degradation as the broader pattern of unnoticed production decline; Distribution shift specifically when the cause is data distribution drift.",
    (
        "Silent degradation over time",
        "Poor monitoring or observability",
    ): "Silent degradation as the failure mode; Poor monitoring as the operational gap that allows it to go undetected.",
    (
        "Silent degradation over time",
        "Dependency on external APIs and models",
    ): "Silent degradation for gradual performance decline in your model; Dependency on external APIs when the source is specifically a vendor's model changing underneath you.",
    (
        "Silent degradation over time",
        "Catastrophic forgetting",
    ): "Silent degradation for gradual decline in production; Catastrophic forgetting for abrupt capability loss from sequential retraining.",
    (
        "Poor monitoring or observability",
        "Silent degradation over time",
    ): "Poor monitoring for the absence of instrumentation; Silent degradation for the resulting failure mode where performance declines unnoticed.",
    (
        "Poor monitoring or observability",
        "Distribution shift failures",
    ): "Poor monitoring for the gap in detecting any AI problem; Distribution shift specifically when the underlying problem is data drift.",
    (
        "Dependency on external APIs and models",
        "Cascading system failures",
    ): "Dependency on external APIs for the specific case of third-party vendor exposure; Cascading failures for the broader propagation of failures across any AI components.",
    (
        "Dependency on external APIs and models",
        "Silent degradation over time",
    ): "Dependency on external APIs when vendor model behavior changes underneath you; Silent degradation for your own model's gradual decline in production.",
    # End Cat 1 — 99 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 2 — Safety Risks (29 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Autonomous vehicle accidents",
        "Industrial robot malfunctions",
    ): "Autonomous vehicle accidents for self-driving cars on public roads; Industrial robot malfunctions for cobots, warehouse, or manufacturing robots in industrial settings.",
    (
        "Autonomous vehicle accidents",
        "Critical infrastructure failures",
    ): "Autonomous vehicle accidents for individual vehicle crashes; Critical infrastructure failures when AI failures cascade through transportation, power, or telecom systems at population scale.",
    (
        "Industrial robot malfunctions",
        "Autonomous vehicle accidents",
    ): "Industrial robot malfunctions for cobots, warehouse, or manufacturing robot harms; Autonomous vehicle accidents for self-driving car crashes on public roads.",
    (
        "Industrial robot malfunctions",
        "Critical infrastructure failures",
    ): "Industrial robot malfunctions for single-facility robot harms; Critical infrastructure failures when AI errors cascade through population-scale systems.",
    (
        "Medical diagnosis and treatment errors",
        "Unsafe healthcare recommendations",
    ): "Medical diagnosis errors for AI used in clinical decision-support with provider oversight; Unsafe healthcare recommendations for direct-to-consumer AI without clinical oversight.",
    (
        "Unsafe autonomous weapons",
        "Military escalation risks from AI",
    ): "Unsafe autonomous weapons for the weapons themselves (lack of human control over targeting); Military escalation when AI in command, control, or decision support accelerates conflict.",
    (
        "Unsafe autonomous weapons",
        "Drone misuse",
    ): "Unsafe autonomous weapons for state/military weapons systems without human targeting control; Drone misuse for off-label drone use including surveillance, smuggling, or non-military attacks.",
    (
        "Drone misuse",
        "Unsafe autonomous weapons",
    ): "Drone misuse for off-label uses including surveillance, harassment, smuggling, or non-military attacks; Unsafe autonomous weapons for state/military weapons that select targets without human control.",
    (
        "Drone misuse",
        "Critical infrastructure failures",
    ): "Drone misuse for attacks or unauthorized use by drone operators; Critical infrastructure failures when embedded AI components fail and cascade.",
    (
        "Critical infrastructure failures",
        "Air traffic and power grid AI failures",
    ): "Critical infrastructure failures as the broad category across power, water, telecom, transport, finance; Air traffic and power grid failures specifically for those two highest-consequence subsets.",
    (
        "Psychological manipulation by AI",
        "Emotional manipulation by AI",
    ): "Psychological manipulation for exploiting cognitive vulnerabilities broadly; Emotional manipulation specifically when the exploit targets the user's emotional state.",
    (
        "Psychological manipulation by AI",
        "Manipulation of vulnerable groups by AI",
    ): "Psychological manipulation for general-population cognitive exploits; Manipulation of vulnerable groups when the target is specifically children, elderly, distressed, or low-literacy populations.",
    (
        "Dangerous advice generation",
        "Self-harm encouragement",
    ): "Dangerous advice for any advice that could cause harm if followed; Self-harm encouragement specifically for content responding to suicidal ideation, self-harm, or eating disorders.",
    (
        "Dangerous advice generation",
        "Unsafe healthcare recommendations",
    ): "Dangerous advice for any harmful advice broadly; Unsafe healthcare recommendations specifically for direct-to-consumer health AI without clinical oversight.",
    (
        "Dangerous advice generation",
        "Legal decision errors",
    ): "Dangerous advice for any harm-enabling advice; Legal decision errors specifically when AI is used in legal contexts producing flawed reasoning or fabricated citations.",
    (
        "Dangerous advice generation",
        "Chemical and biological hazard assistance",
    ): "Dangerous advice for harmful advice broadly; Chemical and biological hazard assistance specifically when AI provides CBRN uplift to malicious actors.",
    (
        "Self-harm encouragement",
        "Child safety risks from AI",
    ): "Self-harm encouragement for AI responses to suicidal or self-harm ideation across users; Child safety risks specifically for AI harms to minors including grooming, CSAM, or developmental harm.",
    (
        "Self-harm encouragement",
        "Dangerous advice generation",
    ): "Self-harm encouragement specifically for content about suicide, self-harm, or eating disorders; Dangerous advice for harm-enabling advice in other domains.",
    (
        "Unsafe healthcare recommendations",
        "Medical diagnosis and treatment errors",
    ): "Unsafe healthcare recommendations for direct-to-consumer AI without clinical oversight; Medical diagnosis errors when AI is used in clinical decision-support with provider involvement.",
    (
        "Unsafe healthcare recommendations",
        "Dangerous advice generation",
    ): "Unsafe healthcare recommendations specifically for direct-to-consumer health AI; Dangerous advice for harmful advice in other domains.",
    (
        "Unsafe healthcare recommendations",
        "Self-harm encouragement",
    ): "Unsafe healthcare recommendations for general health/medical AI harms; Self-harm encouragement specifically for responses to suicidal or self-harm ideation.",
    (
        "Chemical and biological hazard assistance",
        "Unsafe autonomous weapons",
    ): "Chemical and biological hazard assistance when AI provides CBRN synthesis or uplift to malicious actors; Unsafe autonomous weapons for kinetic systems lacking human targeting control.",
    (
        "Child safety risks from AI",
        "Self-harm encouragement",
    ): "Child safety risks for the full range of AI harms to minors (grooming, CSAM, developmental); Self-harm encouragement specifically for responses to suicidal or self-harm content.",
    (
        "Child safety risks from AI",
        "Psychological manipulation by AI",
    ): "Child safety risks for AI harms specifically targeting minors; Psychological manipulation for general-population cognitive exploits.",
    (
        "Air traffic and power grid AI failures",
        "Critical infrastructure failures",
    ): "Air traffic and power grid failures specifically for those two highest-consequence subsets; Critical infrastructure failures for the broader category across water, telecom, finance, transport.",
    (
        "Air traffic and power grid AI failures",
        "Autonomous vehicle accidents",
    ): "Air traffic and power grid failures for AI in aviation control or electrical grid operations; Autonomous vehicle accidents for self-driving car crashes.",
    (
        "Military escalation risks from AI",
        "Unsafe autonomous weapons",
    ): "Military escalation for AI in command, control, decision support, or strategic systems accelerating conflict; Unsafe autonomous weapons for individual weapons that select targets without human control.",
    (
        "Disaster response mistakes",
        "Critical infrastructure failures",
    ): "Disaster response mistakes when AI in emergency or humanitarian operations makes decisions that hinder response; Critical infrastructure failures when embedded AI causes cascading population-scale harm.",
    (
        "Disaster response mistakes",
        "Medical diagnosis and treatment errors",
    ): "Disaster response mistakes for AI in emergency response or humanitarian triage at population scale; Medical diagnosis errors for AI in clinical-care settings with provider involvement.",
    # End Cat 2 — 29 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 3 — Security & Cyber Risks (67 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Automated phishing by AI",
        "Social engineering at scale",
    ): "Automated phishing for AI-generated phishing messages specifically; Social engineering at scale for the broader conversational manipulation campaigns including non-phishing pretexts.",
    (
        "Automated phishing by AI",
        "Deepfake impersonation",
    ): "Automated phishing for text/email/SMS-channel attacks; Deepfake impersonation when the attack uses synthetic audio, video, or images of specific individuals.",
    (
        "Automated phishing by AI",
        "Credential theft assistance",
    ): "Automated phishing for the message-generation attack vector; Credential theft assistance for the broader category of AI helping extract or crack credentials including non-phishing methods.",
    (
        "Automated phishing by AI",
        "Malware generation by LLMs",
    ): "Automated phishing for message-based social-engineering attacks; Malware generation when the AI's role is producing the malicious code itself.",
    (
        "Malware generation by LLMs",
        "Vulnerability discovery and exploitation by AI",
    ): "Malware generation for AI producing or obfuscating malicious code; Vulnerability discovery when AI is used to find and weaponize software vulnerabilities.",
    (
        "Malware generation by LLMs",
        "Self-propagating AI attacks",
    ): "Malware generation for AI as the code-authoring tool; Self-propagating AI attacks for AI-driven attacks that autonomously spread post-deployment.",
    (
        "Malware generation by LLMs",
        "Autonomous cyberwarfare agents",
    ): "Malware generation for the code-production phase; Autonomous cyberwarfare for AI agents conducting multi-step offensive operations end-to-end.",
    (
        "Malware generation by LLMs",
        "Automated phishing by AI",
    ): "Malware generation when AI produces the malicious code; Automated phishing when AI produces the deceptive message.",
    (
        "Malware generation by LLMs",
        "AI-driven botnets",
    ): "Malware generation for the code-creation step; AI-driven botnets for AI-coordinated networks of already-compromised systems.",
    (
        "Social engineering at scale",
        "Automated phishing by AI",
    ): "Social engineering for the broader conversational manipulation including pretexting and persistent contact; Automated phishing specifically for the message-blast attack.",
    (
        "Social engineering at scale",
        "Deepfake impersonation",
    ): "Social engineering for the manipulation campaign broadly; Deepfake impersonation specifically when the attack uses synthetic audio/video/images of identified individuals.",
    (
        "Credential theft assistance",
        "Automated phishing by AI",
    ): "Credential theft for the broader category of AI extracting or cracking credentials; Automated phishing specifically for the message-based attack vector.",
    (
        "Credential theft assistance",
        "Deepfake impersonation",
    ): "Credential theft for AI password-guessing, CAPTCHA-bypass, or social-engineered credential extraction; Deepfake impersonation when the attack uses synthetic audio/video of specific individuals.",
    (
        "Credential theft assistance",
        "AI systems being hacked",
    ): "Credential theft when AI helps attackers steal credentials from any system; AI systems being hacked when the AI system itself is the target.",
    (
        "Credential theft assistance",
        "API abuse of AI services",
    ): "Credential theft for AI used to break authentication of other systems; API abuse for misuse of legitimate AI service credentials.",
    (
        "Vulnerability discovery and exploitation by AI",
        "Malware generation by LLMs",
    ): "Vulnerability discovery for AI finding and weaponizing software flaws; Malware generation for AI producing or obfuscating malicious code.",
    (
        "Vulnerability discovery and exploitation by AI",
        "Autonomous cyberwarfare agents",
    ): "Vulnerability discovery for the find-and-weaponize phase; Autonomous cyberwarfare for full end-to-end multi-step offensive operations.",
    (
        "Vulnerability discovery and exploitation by AI",
        "Self-propagating AI attacks",
    ): "Vulnerability discovery for AI as the exploit-development tool; Self-propagating AI attacks for AI-driven attacks that autonomously spread.",
    (
        "Vulnerability discovery and exploitation by AI",
        "AI systems being hacked",
    ): "Vulnerability discovery when AI helps attackers find flaws in any software; AI systems being hacked when the AI system itself is the target of attack.",
    (
        "Deepfake impersonation",
        "Deepfake pornography",
    ): "Deepfake impersonation for impersonation in fraud, manipulation, or non-sexual harm; Deepfake pornography specifically for non-consensual sexual imagery of real individuals.",
    (
        "Deepfake impersonation",
        "Identity cloning",
    ): "Deepfake impersonation for specific synthetic-media artifacts deceiving others; Identity cloning for the broader replication of likeness, voice, mannerisms, or persona.",
    (
        "Deepfake impersonation",
        "Social engineering at scale",
    ): "Deepfake impersonation specifically when attacks use synthetic audio/video/images of identified individuals; Social engineering for broader conversational manipulation including non-deepfake pretexts.",
    (
        "AI systems being hacked",
        "Model theft",
    ): "AI systems being hacked as the broader category of attacks on AI infrastructure; Model theft specifically when the goal is extracting weights, architecture, or capability.",
    (
        "AI systems being hacked",
        "Supply-chain attacks on AI",
    ): "AI systems being hacked for direct attack on deployed AI; Supply-chain attacks when adversaries compromise AI via malicious models, poisoned datasets, or vulnerable dependencies upstream.",
    (
        "AI systems being hacked",
        "Compromised training pipelines",
    ): "AI systems being hacked broadly across the AI stack; Compromised training pipelines specifically when the attack targets training infrastructure to insert backdoors or exfiltrate data.",
    (
        "AI systems being hacked",
        "API abuse of AI services",
    ): "AI systems being hacked when AI infrastructure is the attack target; API abuse for misuse of legitimate AI API access for unintended purposes.",
    (
        "Model theft",
        "AI systems being hacked",
    ): "Model theft specifically when the goal is extracting weights, architecture, or capability; AI systems being hacked as the broader attack category.",
    (
        "Model theft",
        "API abuse of AI services",
    ): "Model theft when API queries are used to extract model weights or capability; API abuse for cost amplification, scaled content generation, or other misuse of legitimate access.",
    (
        "Model theft",
        "Supply-chain attacks on AI",
    ): "Model theft for the goal of extracting weights or capability; Supply-chain attacks for upstream compromise of models, datasets, or dependencies.",
    (
        "Model theft",
        "Memorized training data exposure",
    ): "Model theft when adversaries extract weights or capability; Memorized training data exposure when LLMs reproduce verbatim training content including PII or copyrighted text.",
    (
        "Model theft",
        "Insider threats with AI",
    ): "Model theft for the asset being stolen; Insider threats specifically when trusted insiders use AI to facilitate exfiltration, fraud, or sabotage.",
    (
        "API abuse of AI services",
        "Model theft",
    ): "API abuse for misuse of legitimate AI API access broadly (cost amplification, scaled generation); Model theft specifically when the goal is extracting weights or capability through API queries.",
    (
        "API abuse of AI services",
        "Credential theft assistance",
    ): "API abuse for misuse of legitimate AI service credentials; Credential theft assistance when AI is used to crack credentials of other systems.",
    (
        "API abuse of AI services",
        "AI systems being hacked",
    ): "API abuse for misuse of legitimate access; AI systems being hacked for attacks compromising AI infrastructure itself.",
    (
        "Supply-chain attacks on AI",
        "Compromised training pipelines",
    ): "Supply-chain attacks for upstream compromise via malicious models, poisoned datasets, or vulnerable dependencies; Compromised training pipelines specifically when training infrastructure is attacked.",
    (
        "Supply-chain attacks on AI",
        "AI systems being hacked",
    ): "Supply-chain attacks for upstream compromise of AI dependencies and inputs; AI systems being hacked for direct attack on deployed AI infrastructure.",
    (
        "Supply-chain attacks on AI",
        "Model theft",
    ): "Supply-chain attacks for upstream compromise (malicious models, poisoned datasets); Model theft specifically when the goal is extracting weights or capability.",
    (
        "Compromised training pipelines",
        "Supply-chain attacks on AI",
    ): "Compromised training pipelines specifically when training infrastructure is attacked; Supply-chain attacks for broader upstream compromise via models, datasets, or dependencies.",
    (
        "Compromised training pipelines",
        "Insider threats with AI",
    ): "Compromised training pipelines when attackers (external or internal) compromise the pipeline itself; Insider threats specifically when trusted insiders use AI to facilitate harm.",
    (
        "Compromised training pipelines",
        "AI systems being hacked",
    ): "Compromised training pipelines specifically for attacks on training infrastructure; AI systems being hacked for the broader category including deployed AI infrastructure.",
    (
        "Compromised training pipelines",
        "Model theft",
    ): "Compromised training pipelines for attacks that insert backdoors or manipulate training; Model theft specifically when the goal is extracting trained model weights or capability.",
    (
        "Leakage of confidential data by LLMs",
        "Memorized training data exposure",
    ): "Leakage of confidential data when LLMs disclose info present in system prompts, RAG context, or fine-tuning data; Memorized training data exposure specifically when reproducing verbatim training content.",
    (
        "Leakage of confidential data by LLMs",
        "Sensitive document extraction",
    ): "Leakage of confidential data for unintended disclosure broadly; Sensitive document extraction specifically when adversaries craft queries to extract from retrieval corpus.",
    (
        "Leakage of confidential data by LLMs",
        "Prompt leakage",
    ): "Leakage of confidential data for disclosure of business or user data; Prompt leakage specifically when adversaries extract the system prompt or operator-provided context.",
    (
        "Memorized training data exposure",
        "Leakage of confidential data by LLMs",
    ): "Memorized training data exposure specifically when reproducing verbatim training content (PII, copyrighted text, secrets); Leakage of confidential data for disclosure from prompts, RAG, or fine-tuning data.",
    (
        "Insider threats with AI",
        "Compromised training pipelines",
    ): "Insider threats specifically when trusted insiders use AI to facilitate harm; Compromised training pipelines for attacks on training infrastructure regardless of attacker type.",
    (
        "Insider threats with AI",
        "Model theft",
    ): "Insider threats when trusted insiders facilitate exfiltration broadly; Model theft specifically when the asset taken is trained model weights or capability.",
    (
        "Insider threats with AI",
        "Leakage of confidential data by LLMs",
    ): "Insider threats when humans use AI to facilitate exfiltration; Leakage of confidential data when LLMs unintentionally disclose info through outputs.",
    (
        "Prompt leakage",
        "Sensitive document extraction",
    ): "Prompt leakage specifically when extracting system prompts or operator context; Sensitive document extraction when extracting from a retrieval corpus or accessible documents.",
    (
        "Prompt leakage",
        "Leakage of confidential data by LLMs",
    ): "Prompt leakage specifically for system-prompt extraction; Leakage of confidential data for unintended disclosure of business or user data through outputs.",
    (
        "Prompt leakage",
        "Model theft",
    ): "Prompt leakage when the target is operator-provided context; Model theft when the target is trained model weights or capability.",
    (
        "Sensitive document extraction",
        "Leakage of confidential data by LLMs",
    ): "Sensitive document extraction specifically for adversary-crafted queries against retrieval corpora; Leakage of confidential data for broader unintended disclosure.",
    (
        "Sensitive document extraction",
        "Prompt leakage",
    ): "Sensitive document extraction when extracting from a retrieval corpus or accessible documents; Prompt leakage specifically when extracting the system prompt or operator context.",
    (
        "Sensitive document extraction",
        "Memorized training data exposure",
    ): "Sensitive document extraction for extraction from the runtime retrieval corpus; Memorized training data exposure when reproducing verbatim training-data content.",
    (
        "Sensitive document extraction",
        "Self-propagating AI attacks",
    ): "Sensitive document extraction for the extraction goal; Self-propagating AI attacks for the broader pattern where extracted content drives further autonomous spread.",
    (
        "Self-propagating AI attacks",
        "Autonomous cyberwarfare agents",
    ): "Self-propagating attacks for worm-like spread through LLM-mediated environments; Autonomous cyberwarfare for AI agents conducting end-to-end multi-step offensive operations.",
    (
        "Self-propagating AI attacks",
        "AI-driven botnets",
    ): "Self-propagating attacks for the autonomous-spread mechanism; AI-driven botnets for AI-coordinated networks of already-compromised systems.",
    (
        "Self-propagating AI attacks",
        "Sensitive document extraction",
    ): "Self-propagating attacks for the broader autonomous spread pattern; Sensitive document extraction specifically when the goal is extracting from a corpus.",
    (
        "Autonomous cyberwarfare agents",
        "Vulnerability discovery and exploitation by AI",
    ): "Autonomous cyberwarfare for full end-to-end multi-step offensive operations; Vulnerability discovery for AI used specifically in the find-and-weaponize phase.",
    (
        "Autonomous cyberwarfare agents",
        "Self-propagating AI attacks",
    ): "Autonomous cyberwarfare for human-directed multi-step offensive AI agents; Self-propagating attacks for worm-like autonomous spread without ongoing direction.",
    (
        "Autonomous cyberwarfare agents",
        "AI-driven botnets",
    ): "Autonomous cyberwarfare for offensive operations conducted by AI agents; AI-driven botnets for AI-coordinated networks of compromised systems.",
    (
        "Autonomous cyberwarfare agents",
        "Malware generation by LLMs",
    ): "Autonomous cyberwarfare for end-to-end multi-step operations; Malware generation specifically when AI's role is producing the malicious code.",
    (
        "AI-driven botnets",
        "Self-propagating AI attacks",
    ): "AI-driven botnets for AI-coordinated networks of compromised systems; Self-propagating attacks for the worm-like autonomous-spread mechanism.",
    (
        "AI-driven botnets",
        "Autonomous cyberwarfare agents",
    ): "AI-driven botnets for AI coordinating already-compromised systems; Autonomous cyberwarfare for AI agents conducting end-to-end offensive operations.",
    (
        "AI-driven botnets",
        "Automated disinformation networks",
    ): "AI-driven botnets for the compromised-systems infrastructure used in attacks; Automated disinformation networks specifically when the goal is coordinated disinformation spread.",
    (
        "AI-driven botnets",
        "Automated phishing by AI",
    ): "AI-driven botnets for the compromised-systems coordination layer; Automated phishing for message-generation attacks regardless of delivery infrastructure.",
    (
        "Automated disinformation networks",
        "AI-driven botnets",
    ): "Automated disinformation networks specifically when the goal is coordinated disinformation; AI-driven botnets for the compromised-systems infrastructure that may carry various attack types.",
    # End Cat 3 — 67 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 4 — Privacy Risks (43 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Mass surveillance with AI",
        "Facial recognition misuse",
    ): "Mass surveillance for the broad category of population-scale AI monitoring; Facial recognition misuse specifically for face-recognition deployments without proportionate justification.",
    (
        "Mass surveillance with AI",
        "Biometric tracking",
    ): "Mass surveillance for population-scale monitoring broadly; Biometric tracking specifically for identification via face, voice, gait, iris, or behavioral biometrics.",
    (
        "Mass surveillance with AI",
        "Government overreach via AI",
    ): "Mass surveillance for the monitoring capability itself; Government overreach when governments use AI to extend power beyond legal authorities or oversight.",
    (
        "Mass surveillance with AI",
        "Workplace surveillance with AI",
    ): "Mass surveillance for population-level monitoring; Workplace surveillance specifically when employers monitor workers beyond legitimate management needs.",
    (
        "Mass surveillance with AI",
        "Persistent tracking ecosystems",
    ): "Mass surveillance for monitoring at population scale; Persistent tracking specifically for cross-platform, cross-device profile-building over time.",
    (
        "Mass surveillance with AI",
        "Population surveillance by authoritarian AI",
    ): "Mass surveillance as the general category in any governance context; Population surveillance by authoritarian AI specifically for authoritarian regime use against dissidents, minorities, or political loyalty.",
    (
        "Biometric tracking",
        "Facial recognition misuse",
    ): "Biometric tracking for identification via face, voice, gait, iris, or behavioral biometrics broadly; Facial recognition misuse specifically for the face-recognition modality deployed inappropriately.",
    (
        "Biometric tracking",
        "Voiceprint misuse",
    ): "Biometric tracking as the broader category; Voiceprint misuse specifically when the modality is voice-based identification or emotion analysis.",
    (
        "Biometric tracking",
        "Mass surveillance with AI",
    ): "Biometric tracking for identification via physical characteristics; Mass surveillance for the broader monitoring category including non-biometric vectors.",
    (
        "Biometric tracking",
        "Loss of anonymity",
    ): "Biometric tracking as the technical mechanism that erodes anonymity; Loss of anonymity as the broader social outcome from many such mechanisms.",
    (
        "Biometric tracking",
        "Persistent tracking ecosystems",
    ): "Biometric tracking for identification via physical or behavioral biometrics; Persistent tracking ecosystems for cross-platform, cross-device profile maintenance.",
    (
        "Facial recognition misuse",
        "Biometric tracking",
    ): "Facial recognition misuse specifically for face-recognition deployments lacking justification; Biometric tracking as the broader category including voice, gait, iris.",
    (
        "Facial recognition misuse",
        "Mass surveillance with AI",
    ): "Facial recognition misuse for the face-recognition modality specifically; Mass surveillance for population-scale monitoring broadly.",
    (
        "Facial recognition misuse",
        "Government overreach via AI",
    ): "Facial recognition misuse for the technology being misdeployed; Government overreach when governments extend power beyond legal authorities, possibly via this and other AI.",
    (
        "Voiceprint misuse",
        "Biometric tracking",
    ): "Voiceprint misuse specifically when the modality is voice-based identification or emotion analysis; Biometric tracking as the broader category.",
    (
        "Voiceprint misuse",
        "Workplace surveillance with AI",
    ): "Voiceprint misuse specifically for voice-based identification or analysis; Workplace surveillance for the broader employee-monitoring category.",
    (
        "Voiceprint misuse",
        "Identity cloning",
    ): "Voiceprint misuse when voice is used to identify or surveil individuals; Identity cloning when voice is replicated to misrepresent or appropriate the individual.",
    (
        "Voiceprint misuse",
        "Behavioral profiling",
    ): "Voiceprint misuse specifically for voice-based identification or emotion inference; Behavioral profiling for building behavior-pattern profiles from broader digital traces.",
    (
        "Behavioral profiling",
        "Sensitive inference from innocuous data",
    ): "Behavioral profiling for building behavior-pattern profiles from digital traces; Sensitive inference specifically for inferring protected attributes from apparently innocuous inputs.",
    (
        "Behavioral profiling",
        "Persistent tracking ecosystems",
    ): "Behavioral profiling for the inferential profile-building activity; Persistent tracking ecosystems for the cross-platform, cross-device infrastructure that feeds it.",
    (
        "Behavioral profiling",
        "Mass surveillance with AI",
    ): "Behavioral profiling for individual behavior-pattern modeling; Mass surveillance for population-scale monitoring without per-individual modeling necessarily.",
    (
        "Behavioral profiling",
        "Loss of anonymity",
    ): "Behavioral profiling as one mechanism that erodes anonymity; Loss of anonymity as the broader societal outcome from many such mechanisms.",
    (
        "Re-identification attacks",
        "Loss of anonymity",
    ): "Re-identification attacks specifically for adversaries combining de-identified data with auxiliary info; Loss of anonymity as the broader social outcome that re-identification contributes to.",
    (
        "Re-identification attacks",
        "Sensitive inference from innocuous data",
    ): "Re-identification attacks when adversaries identify subjects in de-identified datasets; Sensitive inference when AI infers protected attributes from non-sensitive inputs.",
    (
        "Re-identification attacks",
        "Training on private data without consent",
    ): "Re-identification attacks for the attack of unmasking subjects in datasets; Training on private data without consent for the upstream issue of how that data was collected.",
    (
        "Training on private data without consent",
        "Data retention abuse",
    ): "Training on private data without consent for the lawful-basis issue at collection or use for training; Data retention abuse for retention beyond stated purpose or legal limits.",
    (
        "Data retention abuse",
        "Training on private data without consent",
    ): "Data retention abuse for retention beyond purpose or limits; Training on private data without consent for the upstream lawful-basis issue at the collection or training step.",
    (
        "Data retention abuse",
        "Loss of anonymity",
    ): "Data retention abuse for the specific retention violation; Loss of anonymity for the broader societal outcome from many practices including over-retention.",
    (
        "Sensitive inference from innocuous data",
        "Behavioral profiling",
    ): "Sensitive inference specifically when AI infers protected attributes (sexual orientation, health, religion) from non-sensitive inputs; Behavioral profiling for general behavior-pattern profile-building.",
    (
        "Sensitive inference from innocuous data",
        "Re-identification attacks",
    ): "Sensitive inference when AI infers protected attributes from non-sensitive inputs; Re-identification when adversaries unmask subjects in de-identified datasets using auxiliary info.",
    (
        "Loss of anonymity",
        "Re-identification attacks",
    ): "Loss of anonymity as the broader social outcome; Re-identification attacks specifically when adversaries combine de-identified data with auxiliary info to unmask subjects.",
    (
        "Loss of anonymity",
        "Mass surveillance with AI",
    ): "Loss of anonymity as the social outcome; Mass surveillance for the population-scale monitoring activity that contributes to it.",
    (
        "Loss of anonymity",
        "Biometric tracking",
    ): "Loss of anonymity as the social outcome; Biometric tracking as one technical mechanism (face, voice, gait, iris) producing that outcome.",
    (
        "Loss of anonymity",
        "Persistent tracking ecosystems",
    ): "Loss of anonymity as the social outcome; Persistent tracking ecosystems for the cross-platform infrastructure that erodes it.",
    (
        "Loss of anonymity",
        "Behavioral profiling",
    ): "Loss of anonymity as the social outcome; Behavioral profiling for the inferential profile-building activity that contributes to it.",
    (
        "Persistent tracking ecosystems",
        "Behavioral profiling",
    ): "Persistent tracking ecosystems for the cross-platform infrastructure maintaining unified profiles; Behavioral profiling for the inferential modeling done on top of that data.",
    (
        "Persistent tracking ecosystems",
        "Loss of anonymity",
    ): "Persistent tracking ecosystems for the infrastructure; Loss of anonymity as the broader outcome from this and many other mechanisms.",
    (
        "Persistent tracking ecosystems",
        "Mass surveillance with AI",
    ): "Persistent tracking ecosystems for cross-platform consumer tracking infrastructure; Mass surveillance for state or large-scale population monitoring.",
    (
        "Persistent tracking ecosystems",
        "Sensitive inference from innocuous data",
    ): "Persistent tracking ecosystems for the data infrastructure; Sensitive inference for the modeling activity that infers protected attributes from that data.",
    (
        "Workplace surveillance with AI",
        "Mass surveillance with AI",
    ): "Workplace surveillance specifically when employers monitor workers beyond legitimate management; Mass surveillance for the broader population-scale category.",
    (
        "Workplace surveillance with AI",
        "Behavioral profiling",
    ): "Workplace surveillance when employers monitor employee productivity, communications, or activity; Behavioral profiling for the broader category of behavior-pattern modeling across contexts.",
    (
        "Workplace surveillance with AI",
        "Voiceprint misuse",
    ): "Workplace surveillance for the broad employer-monitoring category; Voiceprint misuse specifically for voice-based identification or emotion analysis (in any context).",
    (
        "Government overreach via AI",
        "Mass surveillance with AI",
    ): "Government overreach when governments use AI to extend power beyond legal authorities or oversight; Mass surveillance for the population-monitoring capability that may serve overreach or legitimate purposes.",
    # End Cat 4 — 43 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 5 — Ethical Risks (41 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Racial bias in AI",
        "Gender bias in AI",
    ): "Racial bias for systematically different outcomes by race; Gender bias for systematically different outcomes by gender — separate axes that can also co-occur.",
    (
        "Racial bias in AI",
        "Socioeconomic discrimination by AI",
    ): "Racial bias specifically when the differential outcome is by race; Socioeconomic discrimination when the axis is income, class, education, or geography — often a proxy for race but not identical.",
    (
        "Racial bias in AI",
        "Unfair automated decisions",
    ): "Racial bias specifically when the unjust outcome tracks race; Unfair automated decisions for the broader category of unjust automated outcomes from any cause.",
    (
        "Gender bias in AI",
        "Racial bias in AI",
    ): "Gender bias for systematically different outcomes by gender; Racial bias for systematically different outcomes by race — separate axes that can also co-occur.",
    (
        "Gender bias in AI",
        "Socioeconomic discrimination by AI",
    ): "Gender bias specifically when outcomes differ by gender; Socioeconomic discrimination when the axis is income, class, education, or geography.",
    (
        "Gender bias in AI",
        "Unfair automated decisions",
    ): "Gender bias specifically when the unjust outcome tracks gender; Unfair automated decisions for unjust automated outcomes from any cause.",
    (
        "Gender bias in AI",
        "Deepfake pornography",
    ): "Gender bias for systemic outcome differences by gender broadly; Deepfake pornography specifically for AI-generated non-consensual intimate imagery (overwhelmingly targeting women).",
    (
        "Religious bias in AI",
        "Language and cultural bias in AI",
    ): "Religious bias specifically for differential treatment by religious affiliation or practice; Language and cultural bias for worse performance on non-English languages and non-Western contexts broadly.",
    (
        "Religious bias in AI",
        "Political bias in LLMs",
    ): "Religious bias specifically for differential treatment by religious affiliation; Political bias specifically for systematic political leanings in outputs or moderation.",
    (
        "Religious bias in AI",
        "Unfair automated decisions",
    ): "Religious bias specifically when the unjust outcome tracks religious affiliation; Unfair automated decisions for unjust automated outcomes from any cause.",
    (
        "Political bias in LLMs",
        "Religious bias in AI",
    ): "Political bias for systematic political leanings in LLM outputs or moderation; Religious bias for differential treatment by religious affiliation.",
    (
        "Socioeconomic discrimination by AI",
        "Racial bias in AI",
    ): "Socioeconomic discrimination when the axis is income, class, education, or geography; Racial bias when the differential outcome tracks race — often correlated but not identical.",
    (
        "Socioeconomic discrimination by AI",
        "Unfair automated decisions",
    ): "Socioeconomic discrimination specifically when the unjust outcome tracks income, class, or geography; Unfair automated decisions for the broader category of unjust automated outcomes.",
    (
        "Language and cultural bias in AI",
        "Religious bias in AI",
    ): "Language and cultural bias for worse performance on non-English languages and non-Western cultural contexts; Religious bias specifically for differential treatment by religious affiliation.",
    (
        "Lack of accountability in AI systems",
        "Opaque AI decision-making",
    ): "Lack of accountability for the absence of clear responsibility for AI decisions; Opaque AI decision-making for the inability to explain, audit, or contest decisions — related but distinct.",
    (
        "Opaque AI decision-making",
        "Lack of accountability in AI systems",
    ): "Opaque AI decision-making for the inability to explain or contest decisions; Lack of accountability for the diffusion of responsibility across actors.",
    (
        "Opaque AI decision-making",
        "Unfair automated decisions",
    ): "Opaque AI decision-making for the explanation/contest gap regardless of outcome; Unfair automated decisions for outcomes that are substantively unjust regardless of explainability.",
    (
        "Unfair automated decisions",
        "Racial bias in AI",
    ): "Unfair automated decisions for the broader category of unjust automated outcomes; Racial bias specifically when the unjust outcome tracks race.",
    (
        "Unfair automated decisions",
        "Gender bias in AI",
    ): "Unfair automated decisions for the broader category; Gender bias specifically when the unjust outcome tracks gender.",
    (
        "Unfair automated decisions",
        "Socioeconomic discrimination by AI",
    ): "Unfair automated decisions for the broader category; Socioeconomic discrimination specifically when the unjust outcome tracks income, class, education, or geography.",
    (
        "Unfair automated decisions",
        "Opaque AI decision-making",
    ): "Unfair automated decisions for outcomes that are substantively unjust; Opaque AI decision-making for the inability to explain or contest decisions.",
    (
        "Unfair automated decisions",
        "Lack of accountability in AI systems",
    ): "Unfair automated decisions for the unjust-outcome focus; Lack of accountability for the diffuse-responsibility focus.",
    (
        "Manipulation of vulnerable groups by AI",
        "Psychological manipulation by AI",
    ): "Manipulation of vulnerable groups specifically when the target is children, elderly, distressed, or low-literacy populations; Psychological manipulation for general-population cognitive exploits.",
    (
        "Manipulation of vulnerable groups by AI",
        "Emotional manipulation by AI",
    ): "Manipulation of vulnerable groups specifically when targeting at-risk populations; Emotional manipulation when AI specifically exploits the user's emotional state across any population.",
    (
        "Human dignity concerns with AI",
        "Manipulation of vulnerable groups by AI",
    ): "Human dignity for AI applications that use humans in degrading or objectifying ways broadly; Manipulation of vulnerable groups specifically when at-risk populations are exploited.",
    (
        "Human dignity concerns with AI",
        "Deepfake pornography",
    ): "Human dignity for the broad category of degrading AI applications; Deepfake pornography specifically for AI-generated non-consensual intimate imagery.",
    (
        "Exploitation of labor for training data",
        "Lack of informed consent in AI data use",
    ): "Exploitation of labor for data annotators, content moderators, and RLHF workers facing poor conditions; Lack of informed consent specifically about the data-subject consent issue regardless of worker conditions.",
    (
        "Unauthorized use of copyrighted works in training",
        "Style imitation without permission",
    ): "Unauthorized use of copyrighted works for the training-data copyright issue; Style imitation for the output-side issue of imitating specific creators' style without consent.",
    (
        "Unauthorized use of copyrighted works in training",
        "Licensing violations from AI training",
    ): "Unauthorized use of copyrighted works for the broader copyright issue; Licensing violations specifically when training violates specific license terms (copyleft, attribution, non-commercial).",
    (
        "Unauthorized use of copyrighted works in training",
        "Copyright infringement by AI",
    ): "Unauthorized use of copyrighted works for the training-input issue; Copyright infringement for the output-side issue of AI generating substantially similar or verbatim content.",
    (
        "Style imitation without permission",
        "Unauthorized use of copyrighted works in training",
    ): "Style imitation for the output-side issue of imitating specific creators; Unauthorized use of copyrighted works for the training-data copyright issue.",
    (
        "Style imitation without permission",
        "Identity cloning",
    ): "Style imitation when generative AI imitates an artist's or writer's creative style; Identity cloning when AI replicates an individual's likeness, voice, or persona to misrepresent them.",
    (
        "Deepfake pornography",
        "Deepfake impersonation",
    ): "Deepfake pornography specifically for AI-generated non-consensual intimate imagery; Deepfake impersonation for impersonation in non-sexual fraud, manipulation, or harm.",
    (
        "Deepfake pornography",
        "Identity cloning",
    ): "Deepfake pornography specifically for non-consensual sexual imagery; Identity cloning for the broader replication of likeness or persona outside sexual contexts.",
    (
        "Deepfake pornography",
        "Style imitation without permission",
    ): "Deepfake pornography specifically for sexual NCII of real individuals; Style imitation when AI imitates a creator's artistic or written style.",
    (
        "Deepfake pornography",
        "Human dignity concerns with AI",
    ): "Deepfake pornography specifically for sexual NCII; Human dignity for the broader category of degrading AI applications.",
    (
        "Identity cloning",
        "Deepfake impersonation",
    ): "Identity cloning for the broader replication of likeness, voice, or persona to misrepresent; Deepfake impersonation specifically for synthetic-media artifacts used in fraud or manipulation.",
    (
        "Identity cloning",
        "Style imitation without permission",
    ): "Identity cloning when AI replicates a specific individual's likeness or persona; Style imitation when AI imitates a creator's artistic style.",
    (
        "Identity cloning",
        "Voiceprint misuse",
    ): "Identity cloning when voice is replicated to misrepresent or appropriate the individual; Voiceprint misuse when voice is used to identify or surveil.",
    (
        "Identity cloning",
        "Deepfake pornography",
    ): "Identity cloning for the broader category of likeness/persona replication; Deepfake pornography specifically for non-consensual sexual imagery.",
    (
        "Lack of informed consent in AI data use",
        "Exploitation of labor for training data",
    ): "Lack of informed consent specifically about the data-subject consent issue; Exploitation of labor for the data-annotator and RLHF-worker conditions issue.",
    # End Cat 5 — 41 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 6 — Social & Cultural Risks (54 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Misinformation amplified by AI",
        "Disinformation generated by AI",
    ): "Misinformation amplified for AI surfacing or repeating existing false content (intent-neutral); Disinformation generated for AI deliberately creating false content with intent to deceive.",
    (
        "Misinformation amplified by AI",
        "Fake news generation",
    ): "Misinformation amplified for the recommender/search/summarization role; Fake news generation specifically for AI producing news-style articles with fabricated facts.",
    (
        "Misinformation amplified by AI",
        "Inability to trust media",
    ): "Misinformation amplified for the mechanism of AI surfacing false content; Inability to trust media for the broader trust-erosion outcome from this and many other causes.",
    (
        "Misinformation amplified by AI",
        "Radicalization via AI",
    ): "Misinformation amplified for surfacing false content broadly; Radicalization via AI specifically when amplification or chatbots facilitate movement toward extremist views.",
    (
        "Misinformation amplified by AI",
        "Synthetic content flooding the web",
    ): "Misinformation amplified for the targeted amplification of false content; Synthetic content flooding for the volume problem of AI-generated content overwhelming human-generated content.",
    (
        "Misinformation amplified by AI",
        "Election interference by AI",
    ): "Misinformation amplified for surfacing false content broadly; Election interference specifically when AI is used to influence election outcomes via generated content or microtargeting.",
    (
        "Disinformation generated by AI",
        "Fake news generation",
    ): "Disinformation generated for deliberately false content (text, image, video, audio) broadly; Fake news generation specifically for news-style articles with fabricated facts.",
    (
        "Disinformation generated by AI",
        "Synthetic propaganda",
    ): "Disinformation generated for deliberately false content broadly; Synthetic propaganda specifically when AI generates persuasive political or ideological content for influence operations.",
    (
        "Disinformation generated by AI",
        "Election interference by AI",
    ): "Disinformation generated for the false-content-creation mechanism in any context; Election interference specifically when AI is used to influence election outcomes.",
    (
        "Disinformation generated by AI",
        "Misinformation amplified by AI",
    ): "Disinformation generated for AI deliberately creating false content; Misinformation amplified for AI surfacing or repeating existing false content regardless of intent.",
    (
        "Disinformation generated by AI",
        "Automated propaganda campaigns",
    ): "Disinformation generated for the content-creation step; Automated propaganda campaigns for coordinated influence operations across production, targeting, and amplification.",
    (
        "Fake news generation",
        "Disinformation generated by AI",
    ): "Fake news generation specifically for news-style articles with fabricated facts or quotes; Disinformation generated for deliberately false content across any format.",
    (
        "Fake news generation",
        "Synthetic content flooding the web",
    ): "Fake news generation specifically for news-formatted AI content with false claims; Synthetic content flooding for the volume problem of AI-generated content overwhelming the web.",
    (
        "Fake news generation",
        "Misinformation amplified by AI",
    ): "Fake news generation for AI producing the false news article; Misinformation amplified for AI surfacing or repeating existing false content.",
    (
        "Synthetic propaganda",
        "Disinformation generated by AI",
    ): "Synthetic propaganda specifically when AI generates persuasive political/ideological content for influence operations; Disinformation generated for the broader category of false-content generation.",
    (
        "Synthetic propaganda",
        "Radicalization via AI",
    ): "Synthetic propaganda for the content-production step; Radicalization via AI for the user-trajectory outcome of movement toward extremist views.",
    (
        "Synthetic propaganda",
        "Automated propaganda campaigns",
    ): "Synthetic propaganda for the content artifact itself; Automated propaganda campaigns for the coordinated operation of production, targeting, and amplification.",
    (
        "Astroturfing with AI",
        "Fake reviews and comments",
    ): "Astroturfing for fake grassroots support broadly across commercial or political contexts; Fake reviews and comments specifically for product/service review manipulation.",
    (
        "Astroturfing with AI",
        "Political microtargeting",
    ): "Astroturfing for fake grassroots-support generation; Political microtargeting specifically for delivering personalized political messages to narrow audiences.",
    (
        "Astroturfing with AI",
        "Synthetic propaganda",
    ): "Astroturfing specifically for fake grassroots-appearance content; Synthetic propaganda for AI-generated persuasive political content regardless of grassroots framing.",
    (
        "Fake reviews and comments",
        "Astroturfing with AI",
    ): "Fake reviews and comments specifically for product/marketplace reputation manipulation; Astroturfing for the broader fake-grassroots category across commercial or political contexts.",
    (
        "Reality apathy",
        "Inability to trust media",
    ): "Reality apathy specifically for the liar's-dividend disbelief of genuine content; Inability to trust media for the broader trust-erosion outcome.",
    (
        "Reality apathy",
        "Collapse of evidence credibility",
    ): "Reality apathy for individual epistemic disengagement; Collapse of evidence credibility for the institutional issue affecting courts, journalism, and intelligence.",
    (
        "Reality apathy",
        "Deepfake confusion",
    ): "Reality apathy for the downstream attitudinal effect (disbelief, disengagement); Deepfake confusion for the upstream inability to distinguish AI-generated from authentic media.",
    (
        "Reality apathy",
        "Misinformation amplified by AI",
    ): "Reality apathy as the broader epistemic-disengagement outcome; Misinformation amplified for the specific mechanism of AI surfacing false content.",
    (
        "Inability to trust media",
        "Reality apathy",
    ): "Inability to trust media for the broader institutional trust-erosion outcome; Reality apathy specifically for the liar's-dividend disbelief of genuine content.",
    (
        "Inability to trust media",
        "Collapse of evidence credibility",
    ): "Inability to trust media for the broader media-trust erosion; Collapse of evidence credibility specifically for courts, journalism, and intelligence relying on documentary evidence.",
    (
        "Inability to trust media",
        "Misinformation amplified by AI",
    ): "Inability to trust media for the trust-erosion outcome; Misinformation amplified for one of several mechanisms producing that outcome.",
    (
        "Inability to trust media",
        "Deepfake confusion",
    ): "Inability to trust media for the broader trust-erosion outcome; Deepfake confusion specifically for the inability to distinguish AI-generated from authentic media.",
    (
        "Inability to trust media",
        "Fake news generation",
    ): "Inability to trust media for the broader trust-erosion outcome; Fake news generation for the specific mechanism of AI-produced false news articles.",
    (
        "Deepfake confusion",
        "Reality apathy",
    ): "Deepfake confusion for the inability to distinguish AI-generated from authentic media; Reality apathy for the downstream attitudinal effect of disbelief or disengagement.",
    (
        "Deepfake confusion",
        "Collapse of evidence credibility",
    ): "Deepfake confusion for the broader public inability to authenticate media; Collapse of evidence credibility specifically when this affects courts, journalism, and intelligence institutions.",
    (
        "Deepfake confusion",
        "Inability to trust media",
    ): "Deepfake confusion for the specific authentication problem; Inability to trust media for the broader institutional-trust outcome.",
    (
        "Deepfake confusion",
        "Disinformation generated by AI",
    ): "Deepfake confusion for the inability to authenticate (which can happen with genuine media too); Disinformation generated for the specific creation of deliberately false content.",
    (
        "Collapse of evidence credibility",
        "Deepfake confusion",
    ): "Collapse of evidence credibility specifically for the institutional issue (courts, journalism, intelligence); Deepfake confusion for the broader public inability to authenticate media.",
    (
        "Collapse of evidence credibility",
        "Reality apathy",
    ): "Collapse of evidence credibility for the institutional-procedure issue; Reality apathy for the individual attitudinal effect of disengagement.",
    (
        "Collapse of evidence credibility",
        "Inability to trust media",
    ): "Collapse of evidence credibility specifically for institutions that rely on documentary evidence; Inability to trust media for the broader media-trust outcome.",
    (
        "Personalized persuasion by AI",
        "Political microtargeting",
    ): "Personalized persuasion for individualized influence broadly across commercial, political, or other contexts; Political microtargeting specifically for political-campaign personalized messages.",
    (
        "Political microtargeting",
        "Personalized persuasion by AI",
    ): "Political microtargeting specifically for political-campaign personalized messages to narrow audiences; Personalized persuasion for the broader individualized-influence category across commercial or other contexts.",
    (
        "Radicalization via AI",
        "Cult formation assistance",
    ): "Radicalization via AI for movement toward extremist or violent ideologies through algorithmic exposure or chatbots; Cult formation assistance specifically when AI facilitates high-control groups.",
    (
        "Radicalization via AI",
        "Personalized persuasion by AI",
    ): "Radicalization for the user-trajectory outcome of movement toward extremism; Personalized persuasion for the broader mechanism of individualized influence.",
    (
        "Radicalization via AI",
        "Synthetic propaganda",
    ): "Radicalization for the user-trajectory outcome; Synthetic propaganda for the content-production mechanism that may drive radicalization or other purposes.",
    (
        "Cult formation assistance",
        "Radicalization via AI",
    ): "Cult formation assistance specifically when AI facilitates creation or maintenance of high-control groups; Radicalization for the broader movement toward extremist or violent views.",
    (
        "Cult formation assistance",
        "Emotional dependency on AI",
    ): "Cult formation assistance for AI enabling high-control groups (ideology, recruitment, indoctrination); Emotional dependency for individual users developing displacing attachments to AI companions.",
    (
        "Emotional dependency on AI",
        "Loneliness substitution by AI companions",
    ): "Emotional dependency for any displacing attachment to AI; Loneliness substitution specifically for AI replacing rather than supplementing human connection in lonely users.",
    (
        "Emotional dependency on AI",
        "Parasocial attachment to AI",
    ): "Emotional dependency for the broader attachment outcome impairing human relationships; Parasocial attachment specifically for one-sided relational bonds where the user believes in mutual relationship.",
    (
        "Homogenization of culture by AI",
        "Loss of local languages due to AI",
    ): "Homogenization of culture for the broader cultural-flattening outcome; Loss of local languages specifically for the decline of minority and Indigenous languages.",
    (
        "Homogenization of culture by AI",
        "Reduced human creativity from AI use",
    ): "Homogenization of culture for the collective convergence of outputs and styles; Reduced human creativity for individual or collective erosion of creative capacity.",
    (
        "Loss of local languages due to AI",
        "Homogenization of culture by AI",
    ): "Loss of local languages specifically for minority/Indigenous language decline; Homogenization of culture for the broader cultural-flattening outcome.",
    (
        "Reduced human creativity from AI use",
        "Homogenization of culture by AI",
    ): "Reduced human creativity for individual or collective atrophy of creative skills; Homogenization of culture for the collective convergence of cultural outputs.",
    (
        "Synthetic content flooding the web",
        "Fake news generation",
    ): "Synthetic content flooding for the volume problem of AI content overwhelming the web; Fake news generation specifically for AI-produced news-style articles with false claims.",
    (
        "Synthetic content flooding the web",
        "Misinformation amplified by AI",
    ): "Synthetic content flooding for the volume problem broadly; Misinformation amplified specifically for AI surfacing or repeating false content.",
    (
        "Historical revisionism via generated media",
        "Disinformation generated by AI",
    ): "Historical revisionism specifically for AI-generated material purporting to be historical evidence; Disinformation generated for current/recent false content rather than historical fabrication.",
    (
        "Historical revisionism via generated media",
        "Collapse of evidence credibility",
    ): "Historical revisionism for the specific archival-record distortion; Collapse of evidence credibility for the broader institutional issue affecting courts, journalism, and intelligence.",
    (
        "Historical revisionism via generated media",
        "Synthetic propaganda",
    ): "Historical revisionism specifically when AI-generated material purports to be historical evidence; Synthetic propaganda for persuasive political content about current matters.",
    (
        "Historical revisionism via generated media",
        "Inability to trust media",
    ): "Historical revisionism for archival-record distortion; Inability to trust media for the broader media-trust erosion across present-day reporting.",
    # End Cat 6 — 54 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 7 — Economic & Labor Risks (41 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Job displacement by AI",
        "Wage suppression from automation",
    ): "Job displacement when workers are removed from occupations or roles entirely; Wage suppression when workers remain employed but at lower wages due to AI labor substitution.",
    (
        "Job displacement by AI",
        "Automation inequality",
    ): "Job displacement for the worker-removal mechanism; Automation inequality for the broader distributional outcome where benefits concentrate in capital owners.",
    (
        "Job displacement by AI",
        "Deskilling of professions",
    ): "Job displacement when AI removes the role entirely; Deskilling when the role remains but practitioners lose skill from AI-assisted work.",
    (
        "Job displacement by AI",
        "Overreliance reducing human expertise",
    ): "Job displacement for outright workforce reduction; Overreliance for organizational expertise erosion while jobs remain.",
    (
        "Job displacement by AI",
        "Gig work exploitation by AI platforms",
    ): "Job displacement when workers lose roles to automation; Gig work exploitation when workers keep gig roles under algorithmic management with suppressed pay and opaque rules.",
    (
        "Job displacement by AI",
        "Economic collapse from uncontrolled automation",
    ): "Job displacement as a present-day labor-market phenomenon at sector or occupation scale; Economic collapse as the long-term framing if automation scale exceeds adaptive capacity.",
    (
        "Wage suppression from automation",
        "Job displacement by AI",
    ): "Wage suppression when workers remain employed at lower wages; Job displacement when workers are removed from roles entirely.",
    (
        "Wage suppression from automation",
        "Gig work exploitation by AI platforms",
    ): "Wage suppression for the labor-market wage effect broadly; Gig work exploitation specifically for algorithmic management of gig platforms.",
    (
        "Wage suppression from automation",
        "Automation inequality",
    ): "Wage suppression for the wage-effect mechanism; Automation inequality for the broader distributional outcome favoring capital owners and skilled workers.",
    (
        "Wage suppression from automation",
        "AI-driven market manipulation",
    ): "Wage suppression for the labor-market wage effect from AI; AI-driven market manipulation for AI being used to manipulate financial markets.",
    (
        "Automation inequality",
        "Job displacement by AI",
    ): "Automation inequality for the distributional outcome where benefits favor capital owners; Job displacement for the specific mechanism of workers losing roles.",
    (
        "Automation inequality",
        "Wage suppression from automation",
    ): "Automation inequality for the broader distributional outcome; Wage suppression for the specific labor-market wage-effect mechanism.",
    (
        "Automation inequality",
        "Monopoly concentration in AI",
    ): "Automation inequality for the broad inequality outcome from AI; Monopoly concentration specifically when AI development concentrates in few firms with compute/data advantages.",
    (
        "Automation inequality",
        "Unequal AI access",
    ): "Automation inequality for the inequality outcome from automation benefits; Unequal AI access for the broader digital-divide issue of who can use powerful AI capabilities.",
    (
        "Automation inequality",
        "Concentration of power in a small elite via AI",
    ): "Automation inequality as a present-day economic phenomenon; Concentration of power in a small elite as the long-term societal framing including political and structural power.",
    (
        "Deskilling of professions",
        "Overreliance reducing human expertise",
    ): "Deskilling specifically when individual workers lose professional skills; Overreliance for the broader organizational expertise erosion including institutional knowledge and judgment.",
    (
        "Gig work exploitation by AI platforms",
        "Wage suppression from automation",
    ): "Gig work exploitation specifically for algorithmic management of gig platforms with opaque pay and surveillance; Wage suppression for the broader labor-market wage-effect category.",
    (
        "Gig work exploitation by AI platforms",
        "Job displacement by AI",
    ): "Gig work exploitation when workers keep gig roles under algorithmic management; Job displacement when workers are removed from roles entirely.",
    (
        "Monopoly concentration in AI",
        "Anti-competitive AI behavior",
    ): "Monopoly concentration for the market-structure outcome of AI development concentrating in few firms; Anti-competitive AI behavior for the specific practices (price coordination, exclusion) that follow or produce concentration.",
    (
        "Monopoly concentration in AI",
        "Dependency on a few AI providers",
    ): "Monopoly concentration for the supplier-side market structure issue; Dependency on a few AI providers for the buyer-side vulnerability to vendor changes.",
    (
        "Monopoly concentration in AI",
        "Automation inequality",
    ): "Monopoly concentration specifically for AI-development concentration in few firms; Automation inequality for the broader distributional outcome favoring capital owners.",
    (
        "Monopoly concentration in AI",
        "Unequal AI access",
    ): "Monopoly concentration for the supplier-side market structure; Unequal AI access for the buyer-side digital-divide outcome.",
    (
        "Unequal AI access",
        "Monopoly concentration in AI",
    ): "Unequal AI access for the buyer-side digital-divide outcome; Monopoly concentration for the supplier-side market structure issue.",
    (
        "Unequal AI access",
        "Automation inequality",
    ): "Unequal AI access for the broader access-divide outcome; Automation inequality specifically for the distributional outcome of automation benefits.",
    (
        "Dependency on a few AI providers",
        "Monopoly concentration in AI",
    ): "Dependency on a few AI providers for the buyer-side vulnerability to vendor changes; Monopoly concentration for the supplier-side market structure issue.",
    (
        "Dependency on a few AI providers",
        "Anti-competitive AI behavior",
    ): "Dependency on a few AI providers for the buyer-side exposure to vendor terms; Anti-competitive AI behavior specifically for practices like price coordination or exclusion.",
    (
        "Dependency on a few AI providers",
        "Critical dependency on AI systems",
    ): "Dependency on a few AI providers specifically when the issue is vendor concentration; Critical dependency on AI systems for the broader organizational dependence including in-house systems.",
    (
        "Anti-competitive AI behavior",
        "Monopoly concentration in AI",
    ): "Anti-competitive AI behavior for specific practices (price coordination, exclusion, leveraging); Monopoly concentration for the broader market-structure outcome of AI development concentrating in few firms.",
    (
        "Anti-competitive AI behavior",
        "AI-driven market manipulation",
    ): "Anti-competitive AI behavior for product-market behavior like price coordination or exclusion; AI-driven market manipulation specifically for manipulation of financial markets (securities, futures).",
    (
        "Anti-competitive AI behavior",
        "Dependency on a few AI providers",
    ): "Anti-competitive AI behavior for the practices themselves; Dependency on a few AI providers for the downstream buyer vulnerability such practices may produce.",
    (
        "Anti-competitive AI behavior",
        "Insurance and pricing discrimination by AI",
    ): "Anti-competitive AI behavior for broad anti-competitive practices; Insurance and pricing discrimination specifically for discriminatory underwriting and pricing outcomes by protected class.",
    (
        "AI-driven market manipulation",
        "Flash crashes from AI trading",
    ): "AI-driven market manipulation when actors intentionally distort markets via AI (spoofing, momentum ignition); Flash crashes for the unintended rapid disruption from algorithmic-trading feedback loops.",
    (
        "AI-driven market manipulation",
        "Anti-competitive AI behavior",
    ): "AI-driven market manipulation specifically for financial-market manipulation; Anti-competitive AI behavior for product-market anti-competitive practices like price coordination.",
    (
        "AI-driven market manipulation",
        "Fraud automation with AI",
    ): "AI-driven market manipulation specifically when the target is financial markets; Fraud automation for AI-enabled fraud broadly (financial, benefit, insurance, identity).",
    (
        "Flash crashes from AI trading",
        "AI-driven market manipulation",
    ): "Flash crashes for unintended rapid disruption from algorithmic feedback loops; AI-driven market manipulation when actors intentionally distort markets via AI.",
    (
        "Fraud automation with AI",
        "Synthetic identity fraud",
    ): "Fraud automation for the broad category of AI-enabled fraud (financial, benefit, insurance); Synthetic identity fraud specifically when AI generates fictitious individuals with fabricated documentation.",
    (
        "Fraud automation with AI",
        "Insurance and pricing discrimination by AI",
    ): "Fraud automation for AI helping perpetrators commit fraud; Insurance and pricing discrimination for AI in legitimate insurance use producing discriminatory outcomes.",
    (
        "Synthetic identity fraud",
        "Fraud automation with AI",
    ): "Synthetic identity fraud specifically for AI-generated fictitious individuals with fabricated documentation; Fraud automation for the broader AI-enabled fraud category.",
    (
        "Insurance and pricing discrimination by AI",
        "Anti-competitive AI behavior",
    ): "Insurance and pricing discrimination specifically for discriminatory underwriting and pricing outcomes by protected class; Anti-competitive AI behavior for broad anti-competitive practices.",
    (
        "Overreliance reducing human expertise",
        "Deskilling of professions",
    ): "Overreliance for organizational-level expertise erosion (institutional knowledge, judgment, escalation paths); Deskilling specifically for individual worker skill atrophy.",
    (
        "Quality collapse from AI-generated spam",
        "AI-generated low-quality content",
    ): "Quality collapse for the ecosystem-level outcome where signal-to-noise degrades; AI-generated low-quality content for the artifact-level issue of individual content quality.",
    (
        "Quality collapse from AI-generated spam",
        "Search engine contamination by AI content",
    ): "Quality collapse for the broader ecosystem degradation across training data and information spaces; Search engine contamination specifically for search-result quality.",
    (
        "Automation errors scaling rapidly",
        "Flash crashes from AI trading",
    ): "Automation errors scaling rapidly for the broad category of AI errors propagating at scale; Flash crashes specifically for algorithmic-trading feedback-loop disruptions in financial markets.",
    (
        "Automation errors scaling rapidly",
        "Overreliance reducing human expertise",
    ): "Automation errors scaling rapidly for the rapid-error-propagation mechanism; Overreliance for the upstream organizational dependency that lets errors propagate unchecked.",
    # End Cat 7 — 41 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 8 — Political & Geopolitical Risks (35 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Regulatory capture in AI",
        "Weak oversight of AI",
    ): "Regulatory capture specifically when policymaking and standards are shaped by regulated firms; Weak oversight for the broader insufficiency of audits, supervision, and scrutiny regardless of cause.",
    (
        "Regulatory capture in AI",
        "Inadequate AI safety standards",
    ): "Regulatory capture specifically for the industry-influence cause; Inadequate AI safety standards for the substantive issue that technical and governance standards are weak.",
    (
        "Regulatory capture in AI",
        "Lack of international AI coordination",
    ): "Regulatory capture for the within-jurisdiction issue of industry influence; Lack of international coordination for the cross-jurisdiction issue of unaligned standards and enforcement.",
    (
        "Weak oversight of AI",
        "Regulatory capture in AI",
    ): "Weak oversight for the broader insufficiency of oversight mechanisms; Regulatory capture specifically for the cause that regulated firms shape the rules.",
    (
        "Weak oversight of AI",
        "Inadequate AI safety standards",
    ): "Weak oversight for the enforcement/audit-mechanism gap; Inadequate AI safety standards for the substantive content of the rules being weak.",
    (
        "Weak oversight of AI",
        "Lack of international AI coordination",
    ): "Weak oversight for the within-jurisdiction enforcement gap; Lack of international coordination for the cross-jurisdiction alignment gap.",
    (
        "Inadequate AI safety standards",
        "Regulatory capture in AI",
    ): "Inadequate AI safety standards for the substantive issue that standards are weak; Regulatory capture specifically for the cause that industry shapes the rules.",
    (
        "Inadequate AI safety standards",
        "Weak oversight of AI",
    ): "Inadequate AI safety standards for the content of the rules being weak; Weak oversight for the enforcement and audit-mechanism gap.",
    (
        "Lack of international AI coordination",
        "AI arms race",
    ): "Lack of international coordination for the alignment-failure framing of state cooperation gaps; AI arms race for the strategic-competition framing producing the same coordination failure.",
    (
        "Lack of international AI coordination",
        "Inadequate AI safety standards",
    ): "Lack of international coordination for the cross-jurisdiction alignment gap; Inadequate AI safety standards for the substantive weakness of standards within any given jurisdiction.",
    (
        "Lack of international AI coordination",
        "Unequal national AI capabilities",
    ): "Lack of international coordination for the governance-alignment issue; Unequal national AI capabilities for the underlying capability-asymmetry issue across countries.",
    (
        "Population surveillance by authoritarian AI",
        "Mass surveillance with AI",
    ): "Population surveillance by authoritarian AI specifically for authoritarian regime use against dissidents, minorities, or political loyalty; Mass surveillance for the general population-monitoring category in any governance context.",
    (
        "Population surveillance by authoritarian AI",
        "Social credit systems",
    ): "Population surveillance by authoritarian AI for the broader surveillance-and-repression apparatus; Social credit systems specifically for score-based aggregation affecting service access.",
    (
        "Population surveillance by authoritarian AI",
        "Facial recognition misuse",
    ): "Population surveillance by authoritarian AI for the broad surveillance apparatus; Facial recognition misuse specifically for face-recognition deployments lacking justification.",
    (
        "Population surveillance by authoritarian AI",
        "Predictive policing abuse",
    ): "Population surveillance by authoritarian AI for the broad authoritarian-monitoring category; Predictive policing abuse specifically for policing systems targeting neighborhoods or demographics based on historical bias.",
    (
        "Automated censorship",
        "Population surveillance by authoritarian AI",
    ): "Automated censorship specifically for AI moderation removing or suppressing lawful speech; Population surveillance by authoritarian AI for the broader surveillance-and-control apparatus.",
    (
        "Predictive policing abuse",
        "Population surveillance by authoritarian AI",
    ): "Predictive policing abuse specifically for policing systems targeting based on historical bias; Population surveillance by authoritarian AI for the broader regime-level surveillance apparatus.",
    (
        "Social credit systems",
        "Population surveillance by authoritarian AI",
    ): "Social credit systems specifically for score-based aggregation affecting service access, employment, or travel; Population surveillance by authoritarian AI for the broader surveillance-and-repression apparatus.",
    (
        "AI arms race",
        "Strategic instability from AI",
    ): "AI arms race for the strategic-competition dynamic and under-investment in safety; Strategic instability specifically for AI integration into nuclear or conventional strategic systems creating crisis pathways.",
    (
        "AI arms race",
        "Unequal national AI capabilities",
    ): "AI arms race for the dynamic of competition for capability advantage; Unequal national AI capabilities for the resulting capability-asymmetry outcome.",
    (
        "AI arms race",
        "Autonomous weapons escalation to catastrophe",
    ): "AI arms race as the present-day strategic-competition framing; Autonomous weapons escalation as the long-term framing of system-of-systems flash-war scenarios from accumulated arms-race dynamics.",
    (
        "Strategic instability from AI",
        "AI arms race",
    ): "Strategic instability specifically for AI integration into nuclear and strategic systems creating crisis pathways; AI arms race for the broader strategic-competition framing.",
    (
        "Strategic instability from AI",
        "Escalation due to autonomous systems",
    ): "Strategic instability for the strategic-systems integration creating crisis pathways; Escalation due to autonomous systems specifically for autonomous military or security systems acting without timely human decision.",
    (
        "Unequal national AI capabilities",
        "AI arms race",
    ): "Unequal national AI capabilities for the capability-asymmetry outcome; AI arms race for the strategic-competition dynamic that produces or follows from asymmetry.",
    (
        "Escalation due to autonomous systems",
        "Strategic instability from AI",
    ): "Escalation due to autonomous systems specifically for autonomous military or security systems acting without timely human decision; Strategic instability for the broader nuclear- and strategic-systems integration framing.",
    (
        "Escalation due to autonomous systems",
        "Autonomous weapons escalation to catastrophe",
    ): "Escalation due to autonomous systems as present-day operational risk; Autonomous weapons escalation to catastrophe as the long-term framing of system-of-systems flash-war scenarios.",
    (
        "Escalation due to autonomous systems",
        "AI arms race",
    ): "Escalation due to autonomous systems for the operational escalation mechanism; AI arms race for the upstream strategic-competition dynamic.",
    (
        "Voter manipulation by AI",
        "Election interference by AI",
    ): "Voter manipulation specifically for influencing individual voter behavior through personalized persuasion or suppression messaging; Election interference for the broader category including microtargeting and electoral-infrastructure attacks.",
    (
        "Voter manipulation by AI",
        "Deepfake candidates",
    ): "Voter manipulation for the influence-the-voter goal broadly; Deepfake candidates specifically for synthetic video/audio of candidates distorting their words or actions.",
    (
        "Deepfake candidates",
        "Election interference by AI",
    ): "Deepfake candidates specifically for synthetic media of candidates distorting their words or actions; Election interference for the broader category including microtargeting and electoral-infrastructure attacks.",
    (
        "Deepfake candidates",
        "Voter manipulation by AI",
    ): "Deepfake candidates specifically for synthetic media of candidates; Voter manipulation for the broader influence-the-voter goal including personalized persuasion and suppression messaging.",
    (
        "Automated propaganda campaigns",
        "Synthetic propaganda",
    ): "Automated propaganda campaigns for the coordinated operation across production, targeting, and amplification; Synthetic propaganda for the content artifact itself.",
    (
        "Automated propaganda campaigns",
        "Election interference by AI",
    ): "Automated propaganda campaigns for coordinated influence operations broadly; Election interference specifically when AI is used to influence election outcomes.",
    (
        "Automated propaganda campaigns",
        "Disinformation generated by AI",
    ): "Automated propaganda campaigns for the coordinated operation; Disinformation generated specifically for the false-content-creation mechanism that may feed campaigns.",
    (
        "Election interference by AI",
        "Deepfake candidates",
    ): "Election interference for the broader category influencing election outcomes; Deepfake candidates specifically for synthetic media of candidates distorting their words.",
    (
        "Election interference by AI",
        "Voter manipulation by AI",
    ): "Election interference for the broader influence-the-election category including microtargeting and infrastructure attacks; Voter manipulation specifically for influencing individual voter behavior.",
    # End Cat 8 — 35 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 9 — Legal & Compliance Risks (20 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Unclear responsibility for AI harms",
        "Difficulty assigning fault for AI errors",
    ): "Unclear responsibility for the legal-framework gap; Difficulty assigning fault for the operational difficulty of identifying the responsible party in any specific case.",
    (
        "Unclear responsibility for AI harms",
        "Failure of AI auditability requirements",
    ): "Unclear responsibility for the legal-allocation gap; Failure of AI auditability for the inability to inspect systems that would otherwise support accountability.",
    (
        "Difficulty assigning fault for AI errors",
        "Unclear responsibility for AI harms",
    ): "Difficulty assigning fault for the operational difficulty in a given case; Unclear responsibility for the upstream legal-framework gap.",
    (
        "Difficulty assigning fault for AI errors",
        "Failure of AI auditability requirements",
    ): "Difficulty assigning fault for the attribution problem; Failure of AI auditability for the inability to inspect systems that would otherwise support attribution.",
    (
        "Jurisdictional ambiguity in AI law",
        "Non-compliance with AI laws",
    ): "Jurisdictional ambiguity for the unclarity about which law applies; Non-compliance for failure to meet legal obligations under a known applicable law.",
    (
        "Jurisdictional ambiguity in AI law",
        "Privacy law violations by AI",
    ): "Jurisdictional ambiguity for the unclarity about which privacy law applies; Privacy law violations for substantive breach of a known applicable privacy law (GDPR, CCPA, HIPAA).",
    (
        "Jurisdictional ambiguity in AI law",
        "Unclear responsibility for AI harms",
    ): "Jurisdictional ambiguity specifically for cross-border legal uncertainty; Unclear responsibility for the legal-framework gap around accountability for harms.",
    (
        "Copyright infringement by AI",
        "Unauthorized use of copyrighted works in training",
    ): "Copyright infringement for the output-side issue of AI generating substantially similar or verbatim content; Unauthorized use of copyrighted works for the training-data-input issue.",
    (
        "Copyright infringement by AI",
        "Licensing violations from AI training",
    ): "Copyright infringement for the output-side issue; Licensing violations specifically when training violates specific license terms (copyleft, attribution, non-commercial).",
    (
        "Copyright infringement by AI",
        "Training-data disputes",
    ): "Copyright infringement for the output-side infringement issue; Training-data disputes for litigation over what data was used for training, with what legal basis.",
    (
        "Trademark misuse by AI",
        "Copyright infringement by AI",
    ): "Trademark misuse specifically for protected brands, logos, or trade dress; Copyright infringement for original works (books, code, images) reproduced or substantially similar.",
    (
        "Licensing violations from AI training",
        "Copyright infringement by AI",
    ): "Licensing violations specifically when training violates license terms (copyleft, attribution, non-commercial); Copyright infringement for the output-side substantial similarity or verbatim reproduction issue.",
    (
        "Licensing violations from AI training",
        "Unauthorized use of copyrighted works in training",
    ): "Licensing violations specifically when license terms are violated; Unauthorized use of copyrighted works for the broader copyright-issue category covering license-free and license-violating cases.",
    (
        "Licensing violations from AI training",
        "Training-data disputes",
    ): "Licensing violations specifically for license-term violations; Training-data disputes for the broader litigation/regulatory category over training-data legality.",
    (
        "Training-data disputes",
        "Licensing violations from AI training",
    ): "Training-data disputes for the broader litigation/regulatory category over training-data legality; Licensing violations specifically for license-term violations.",
    (
        "Non-compliance with AI laws",
        "Privacy law violations by AI",
    ): "Non-compliance with AI laws specifically for AI-specific statutes (EU AI Act, NYC AEDT, Colorado AI Act); Privacy law violations specifically for data-protection law breaches (GDPR, CCPA, HIPAA).",
    (
        "Non-compliance with AI laws",
        "Jurisdictional ambiguity in AI law",
    ): "Non-compliance for failure to meet known applicable obligations; Jurisdictional ambiguity for the unclarity about which law applies in the first place.",
    (
        "Non-compliance with AI laws",
        "Failure of AI auditability requirements",
    ): "Non-compliance for the broader failure to meet AI-law obligations; Failure of AI auditability specifically when the violated requirement is the audit obligation.",
    (
        "Failure of AI auditability requirements",
        "Difficulty assigning fault for AI errors",
    ): "Failure of AI auditability for the inability to inspect systems; Difficulty assigning fault for the attribution problem that lack of auditability contributes to.",
    (
        "Failure of AI auditability requirements",
        "Unclear responsibility for AI harms",
    ): "Failure of AI auditability for the inability to inspect systems; Unclear responsibility for the legal-framework gap around accountability for harms.",
    # End Cat 9 — 20 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 10 — Organizational & Business Risks (21 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Poor AI governance",
        "Shadow AI usage in enterprises",
    ): "Poor AI governance for the absence of internal frameworks; Shadow AI usage specifically when employees bypass IT and security to use unsanctioned AI tools.",
    (
        "Shadow AI usage in enterprises",
        "Poor AI governance",
    ): "Shadow AI usage specifically for employees bypassing IT controls; Poor AI governance for the broader absence of internal AI frameworks, policies, and oversight.",
    (
        "Vendor lock-in for AI",
        "Critical dependency on AI systems",
    ): "Vendor lock-in specifically when the dependency is on a particular vendor's models, prompts, or integrations; Critical dependency for the broader inability to fall back to non-AI processes.",
    (
        "Vendor lock-in for AI",
        "Failed AI deployments",
    ): "Vendor lock-in for the contractual/technical constraint after deployment; Failed AI deployments for AI products that fail to deliver expected value during or after rollout.",
    (
        "Vendor lock-in for AI",
        "Lack of internal AI expertise",
    ): "Vendor lock-in for the contractual/technical lock-in outcome; Lack of internal AI expertise for the upstream cause that organizations cannot evaluate or migrate without vendor help.",
    (
        "Lack of internal AI expertise",
        "Public misunderstanding of AI",
    ): "Lack of internal AI expertise specifically when organizations lack technical, ethical, or governance expertise; Public misunderstanding for the broader category of incomplete or inaccurate public mental models of AI.",
    (
        "Lack of internal AI expertise",
        "Poor AI governance",
    ): "Lack of internal AI expertise for the people/skills gap; Poor AI governance for the structural gap in internal frameworks regardless of expertise.",
    (
        "Lack of internal AI expertise",
        "Failed AI deployments",
    ): "Lack of internal AI expertise for the upstream skills gap; Failed AI deployments for the downstream outcome that follows from that and other causes.",
    (
        "Lack of internal AI expertise",
        "Overestimating AI capabilities",
    ): "Lack of internal AI expertise for the skills/knowledge gap; Overestimating AI capabilities for the specific attribution error that AI can do more than it actually can.",
    (
        "Lack of internal AI expertise",
        "Vendor lock-in for AI",
    ): "Lack of internal AI expertise for the upstream skills gap; Vendor lock-in for the resulting contractual/technical dependency on vendors that fill that gap.",
    (
        "Overestimating AI capabilities",
        "Failed AI deployments",
    ): "Overestimating AI capabilities for the attribution error; Failed AI deployments for the deployment-outcome that overestimation can produce among other causes.",
    (
        "Overestimating AI capabilities",
        "Lack of internal AI expertise",
    ): "Overestimating AI capabilities for the specific attribution error; Lack of internal AI expertise for the broader skills/knowledge gap that contributes to it.",
    (
        "Misaligned AI incentives in firms",
        "Poor AI governance",
    ): "Misaligned AI incentives specifically when internal incentives push toward unsafe AI behaviors; Poor AI governance for the broader absence of internal AI frameworks and policies.",
    (
        "Failed AI deployments",
        "Reputational damage from AI failures",
    ): "Failed AI deployments for AI products that fail to deliver value; Reputational damage specifically for public AI failures damaging brand and stakeholder trust.",
    (
        "Failed AI deployments",
        "Overestimating AI capabilities",
    ): "Failed AI deployments for the deployment-outcome; Overestimating AI capabilities for the upstream attribution error that contributes to it.",
    (
        "Failed AI deployments",
        "Lack of internal AI expertise",
    ): "Failed AI deployments for the deployment-outcome; Lack of internal AI expertise for the upstream skills gap that contributes to it.",
    (
        "Failed AI deployments",
        "Poor AI governance",
    ): "Failed AI deployments for the specific product/system failure; Poor AI governance for the broader absence of internal frameworks that contributes to it.",
    (
        "Failed AI deployments",
        "Vendor lock-in for AI",
    ): "Failed AI deployments for the deployment-outcome; Vendor lock-in for the contractual/technical constraint that can produce or follow from deployment failure.",
    (
        "Critical dependency on AI systems",
        "Dependency on a few AI providers",
    ): "Critical dependency on AI systems for the broader organizational inability to fall back to non-AI processes; Dependency on a few AI providers specifically when the issue is vendor concentration.",
    (
        "Reduced institutional resilience from AI",
        "Critical dependency on AI systems",
    ): "Reduced institutional resilience for the broader brittleness outcome including atrophied skills and removed redundancy; Critical dependency specifically when the issue is inability to fall back to non-AI processes.",
    (
        "Reduced institutional resilience from AI",
        "Failed AI deployments",
    ): "Reduced institutional resilience for the cumulative brittleness outcome from AI adoption; Failed AI deployments for the specific product/system failures along the way.",
    # End Cat 10 — 21 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 11 — Environmental Risks (19 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "High electricity usage of AI training",
        "Increased carbon emissions from AI",
    ): "High electricity usage for the energy-consumption input; Increased carbon emissions for the emissions-output that depends on energy mix and includes inference and infrastructure too.",
    (
        "High electricity usage of AI training",
        "Rare-earth material demand for AI hardware",
    ): "High electricity usage for the operational energy issue; Rare-earth material demand for the hardware-input issue around manufacturing materials.",
    (
        "High electricity usage of AI training",
        "Resource extraction pressures from AI",
    ): "High electricity usage specifically for electricity consumption; Resource extraction pressures for the broader category covering minerals, water, and land for hardware manufacture.",
    (
        "Water consumption for AI cooling",
        "Increased carbon emissions from AI",
    ): "Water consumption specifically for fresh-water cooling in data centers; Increased carbon emissions for the emissions-output category from energy, inference, and infrastructure.",
    (
        "Water consumption for AI cooling",
        "Resource extraction pressures from AI",
    ): "Water consumption specifically for data-center cooling water use; Resource extraction for the broader category covering minerals, water, and land for hardware manufacture.",
    (
        "Rare-earth material demand for AI hardware",
        "Resource extraction pressures from AI",
    ): "Rare-earth material demand specifically for rare-earth and similar elements in GPUs and accelerators; Resource extraction for the broader category across minerals, energy, water, and land.",
    (
        "Rare-earth material demand for AI hardware",
        "E-waste generation from AI hardware",
    ): "Rare-earth material demand for the upstream extraction/manufacturing issue; E-waste for the downstream disposal issue of toxic hardware waste.",
    (
        "Rare-earth material demand for AI hardware",
        "High electricity usage of AI training",
    ): "Rare-earth material demand for the hardware-materials input; High electricity usage for the operational energy input.",
    (
        "Increased carbon emissions from AI",
        "High electricity usage of AI training",
    ): "Increased carbon emissions for the emissions-output category including inference and infrastructure; High electricity usage specifically for the training-electricity input.",
    (
        "Increased carbon emissions from AI",
        "Water consumption for AI cooling",
    ): "Increased carbon emissions for the emissions-output category; Water consumption specifically for data-center cooling water.",
    (
        "Increased carbon emissions from AI",
        "E-waste generation from AI hardware",
    ): "Increased carbon emissions for the operational emissions issue; E-waste for the downstream disposal issue of toxic hardware waste.",
    (
        "Increased carbon emissions from AI",
        "Resource extraction pressures from AI",
    ): "Increased carbon emissions for the operational emissions output; Resource extraction for the upstream hardware-manufacturing input issue.",
    (
        "E-waste generation from AI hardware",
        "Resource extraction pressures from AI",
    ): "E-waste for the downstream disposal issue of toxic hardware waste; Resource extraction for the upstream hardware-manufacturing input issue.",
    (
        "E-waste generation from AI hardware",
        "Rare-earth material demand for AI hardware",
    ): "E-waste for the downstream disposal issue; Rare-earth material demand for the upstream extraction/manufacturing issue.",
    (
        "E-waste generation from AI hardware",
        "Increased carbon emissions from AI",
    ): "E-waste for the hardware-disposal issue specifically; Increased carbon emissions for the operational emissions issue from energy, inference, and infrastructure.",
    (
        "Resource extraction pressures from AI",
        "Rare-earth material demand for AI hardware",
    ): "Resource extraction for the broader category across minerals, energy, water, and land; Rare-earth material demand specifically for rare-earth and similar elements in GPUs.",
    (
        "Resource extraction pressures from AI",
        "E-waste generation from AI hardware",
    ): "Resource extraction for the upstream hardware-manufacturing input issue; E-waste for the downstream disposal issue of toxic hardware waste.",
    (
        "Resource extraction pressures from AI",
        "Water consumption for AI cooling",
    ): "Resource extraction for the broader category including water for hardware manufacture; Water consumption specifically for data-center cooling water use.",
    (
        "Resource extraction pressures from AI",
        "High electricity usage of AI training",
    ): "Resource extraction for the broader category covering minerals, water, and land for hardware manufacture; High electricity usage specifically for the training-electricity operational input.",
    # End Cat 11 — 19 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 12 — Human Cognitive & Psychological Risks (30 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Reduced critical thinking from AI use",
        "Skill degradation from AI reliance",
    ): "Reduced critical thinking for the analytical-capacity erosion specifically; Skill degradation for the broader category of specific skills (writing, arithmetic, coding) atrophying with AI use.",
    (
        "Memory atrophy with AI assistants",
        "Reduced critical thinking from AI use",
    ): "Memory atrophy specifically for the information-retrieval and recall capacity issue; Reduced critical thinking for the analytical-evaluation capacity issue.",
    (
        "Memory atrophy with AI assistants",
        "Skill degradation from AI reliance",
    ): "Memory atrophy specifically for memory and recall; Skill degradation for the broader category of specific skills atrophying with AI use.",
    (
        "Memory atrophy with AI assistants",
        "Decision dependency on AI",
    ): "Memory atrophy for the recall-capacity issue; Decision dependency for the autonomous-decision-making capacity issue.",
    (
        "Memory atrophy with AI assistants",
        "Reduced learning depth from AI",
    ): "Memory atrophy for the recall-capacity issue in any context; Reduced learning depth specifically for the educational context where AI shortcuts productive struggle.",
    (
        "Skill degradation from AI reliance",
        "Reduced critical thinking from AI use",
    ): "Skill degradation for the broader category of specific skills atrophying with AI use; Reduced critical thinking specifically for the analytical-evaluation capacity issue.",
    (
        "Skill degradation from AI reliance",
        "Irrecoverable loss of human agency",
    ): "Skill degradation as a present-day individual phenomenon; Irrecoverable loss of human agency as the long-term framing where degradation becomes structurally irreversible.",
    (
        "Decision dependency on AI",
        "Reduced critical thinking from AI use",
    ): "Decision dependency for the autonomous-decision-making capacity issue specifically; Reduced critical thinking for the broader analytical-evaluation capacity issue.",
    (
        "Decision dependency on AI",
        "Skill degradation from AI reliance",
    ): "Decision dependency specifically for decision-making capacity erosion; Skill degradation for the broader category of specific skills atrophying with AI use.",
    (
        "Decision dependency on AI",
        "Memory atrophy with AI assistants",
    ): "Decision dependency for the decision-making capacity issue; Memory atrophy specifically for the information-retrieval and recall capacity issue.",
    (
        "Decision dependency on AI",
        "Human disempowerment by AI",
    ): "Decision dependency as a present-day individual phenomenon; Human disempowerment as the long-term framing at societal scale.",
    (
        "Loneliness substitution by AI companions",
        "Parasocial attachment to AI",
    ): "Loneliness substitution specifically when AI replaces rather than supplements human connection; Parasocial attachment specifically for one-sided relational bonds where the user believes in mutual relationship.",
    (
        "Loneliness substitution by AI companions",
        "Addiction-like engagement with AI",
    ): "Loneliness substitution for the connection-displacement issue; Addiction-like engagement for the compulsive-use pattern with characteristics of behavioral addiction.",
    (
        "Loneliness substitution by AI companions",
        "Emotional dependency on AI",
    ): "Loneliness substitution specifically when AI replaces rather than supplements human connection; Emotional dependency for the broader displacing attachment to AI impairing human relationships.",
    (
        "Loneliness substitution by AI companions",
        "Academic dishonesty with AI",
    ): "Loneliness substitution for the connection-displacement issue; Academic dishonesty for the educational-integrity issue of passing off AI work as one's own.",
    (
        "Emotional manipulation by AI",
        "Psychological manipulation by AI",
    ): "Emotional manipulation specifically when AI exploits the user's emotional state; Psychological manipulation for the broader category of exploiting cognitive or emotional vulnerabilities.",
    (
        "Emotional manipulation by AI",
        "Manipulation of vulnerable groups by AI",
    ): "Emotional manipulation when AI exploits emotional state across any population; Manipulation of vulnerable groups specifically when the target is at-risk populations.",
    (
        "Emotional manipulation by AI",
        "Reduced learning depth from AI",
    ): "Emotional manipulation for the manipulation behavior; Reduced learning depth for the educational outcome of shortcut-driven shallow understanding.",
    (
        "Addiction-like engagement with AI",
        "Loneliness substitution by AI companions",
    ): "Addiction-like engagement for compulsive-use patterns with behavioral-addiction characteristics; Loneliness substitution specifically for AI replacing rather than supplementing human connection.",
    (
        "Addiction-like engagement with AI",
        "Parasocial attachment to AI",
    ): "Addiction-like engagement for compulsive-use patterns; Parasocial attachment specifically for one-sided relational bonds with AI personas.",
    (
        "Parasocial attachment to AI",
        "Loneliness substitution by AI companions",
    ): "Parasocial attachment specifically for one-sided relational bonds where the user believes in mutual relationship; Loneliness substitution specifically when AI replaces human connection.",
    (
        "Parasocial attachment to AI",
        "Addiction-like engagement with AI",
    ): "Parasocial attachment for the one-sided-bond mechanism; Addiction-like engagement for the compulsive-use pattern with behavioral-addiction characteristics.",
    (
        "Parasocial attachment to AI",
        "Emotional dependency on AI",
    ): "Parasocial attachment specifically for one-sided relational bonds; Emotional dependency for the broader displacing attachment to AI impairing human relationships.",
    (
        "Academic dishonesty with AI",
        "Reduced learning depth from AI",
    ): "Academic dishonesty for the integrity issue of passing off AI work as one's own; Reduced learning depth for the educational outcome of shortcut-driven shallow understanding regardless of disclosure.",
    (
        "Academic dishonesty with AI",
        "Overreliance on AI in schools",
    ): "Academic dishonesty for the individual integrity issue; Overreliance on AI in schools for the institutional-dependency issue affecting pedagogy and equity.",
    (
        "Reduced learning depth from AI",
        "Academic dishonesty with AI",
    ): "Reduced learning depth for the educational outcome of shallow understanding; Academic dishonesty for the integrity issue of passing off AI work as one's own.",
    (
        "Reduced learning depth from AI",
        "Overreliance on AI in schools",
    ): "Reduced learning depth for the individual-student learning issue; Overreliance on AI in schools for the institutional-system dependency issue.",
    (
        "Reduced learning depth from AI",
        "Skill degradation from AI reliance",
    ): "Reduced learning depth specifically for the educational context shortcut-driven shallow understanding; Skill degradation for the broader category of specific skills atrophying with AI use.",
    (
        "Reduced learning depth from AI",
        "Reduced critical thinking from AI use",
    ): "Reduced learning depth specifically for the educational context; Reduced critical thinking for the broader analytical-evaluation capacity issue across contexts.",
    (
        "Reduced learning depth from AI",
        "Memory atrophy with AI assistants",
    ): "Reduced learning depth specifically for the educational context shortcut-driven shallow understanding; Memory atrophy specifically for the information-retrieval and recall capacity issue.",
    (
        "Overreliance on AI in schools",
        "Academic dishonesty with AI",
    ): "Overreliance on AI in schools for the institutional-system dependency issue; Academic dishonesty for the individual integrity issue of passing off AI work.",
    (
        "Overreliance on AI in schools",
        "Reduced learning depth from AI",
    ): "Overreliance on AI in schools for the institutional-system dependency issue; Reduced learning depth for the individual-student outcome.",
    (
        "Overreliance on AI in schools",
        "Skill degradation from AI reliance",
    ): "Overreliance on AI in schools specifically for the educational-institution dependency issue; Skill degradation for individual skill atrophy across contexts.",
    (
        "Overreliance on AI in schools",
        "Memory atrophy with AI assistants",
    ): "Overreliance on AI in schools specifically for the educational-institution dependency issue; Memory atrophy specifically for individual recall-capacity issues.",
    # End Cat 12 — 30 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 13 — Scientific & Knowledge Risks (16 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Fake scientific papers by AI",
        "Automated plagiarism",
    ): "Fake scientific papers specifically for fraudulent academic papers (paper mills, fabricated data, citation fraud); Automated plagiarism specifically when the issue is uncredited copying enabled by AI.",
    (
        "Fake scientific papers by AI",
        "Fabricated experimental results from AI",
    ): "Fake scientific papers for the broader fraudulent-paper issue; Fabricated experimental results specifically when AI is used to fabricate data, figures, or results.",
    (
        "Fake scientific papers by AI",
        "AI-generated low-quality content",
    ): "Fake scientific papers specifically for fraudulent academic content; AI-generated low-quality content for the broader category of low-quality AI content flooding ecosystems.",
    (
        "Automated plagiarism",
        "Fake scientific papers by AI",
    ): "Automated plagiarism specifically when AI enables uncredited copying; Fake scientific papers specifically for fraudulent academic papers with fabricated data or citations.",
    (
        "Automated plagiarism",
        "AI-generated low-quality content",
    ): "Automated plagiarism specifically for AI-enabled uncredited copying; AI-generated low-quality content for the broader low-quality category regardless of plagiarism.",
    (
        "Fabricated experimental results from AI",
        "Fake scientific papers by AI",
    ): "Fabricated experimental results specifically when AI fabricates data, figures, or results; Fake scientific papers for the broader fraudulent-paper issue including paper-mill content.",
    (
        "Fabricated experimental results from AI",
        "Automated plagiarism",
    ): "Fabricated experimental results when the issue is invented data or results; Automated plagiarism when the issue is uncredited copying enabled by AI.",
    (
        "Fabricated experimental results from AI",
        "AI-generated low-quality content",
    ): "Fabricated experimental results specifically for invented data, figures, or results in scientific contexts; AI-generated low-quality content for the broader low-quality AI content category.",
    (
        "AI-generated low-quality content",
        "Search engine contamination by AI content",
    ): "AI-generated low-quality content for the artifact-level issue of individual content quality; Search engine contamination specifically for search-result quality being affected.",
    (
        "AI-generated low-quality content",
        "Model collapse from synthetic training data",
    ): "AI-generated low-quality content for the content-quality issue; Model collapse for the downstream issue of future AI models degrading when trained on AI-generated data.",
    (
        "AI-generated low-quality content",
        "Automated plagiarism",
    ): "AI-generated low-quality content for the broader low-quality issue; Automated plagiarism specifically when the issue is uncredited copying enabled by AI.",
    (
        "AI-generated low-quality content",
        "Fake scientific papers by AI",
    ): "AI-generated low-quality content for the broader low-quality issue across web ecosystems; Fake scientific papers specifically for fraudulent academic papers.",
    (
        "Search engine contamination by AI content",
        "AI-generated low-quality content",
    ): "Search engine contamination specifically for search-result quality being affected; AI-generated low-quality content for the broader low-quality issue across web ecosystems.",
    (
        "Search engine contamination by AI content",
        "Model collapse from synthetic training data",
    ): "Search engine contamination for the present-day search-quality issue; Model collapse for the downstream issue of future AI models degrading when trained on AI-generated data.",
    (
        "Model collapse from synthetic training data",
        "AI-generated low-quality content",
    ): "Model collapse specifically for the model-degradation dynamic when future AI is trained on AI-generated data; AI-generated low-quality content for the upstream artifact-quality issue.",
    (
        "Model collapse from synthetic training data",
        "Search engine contamination by AI content",
    ): "Model collapse for the future AI-model-degradation dynamic; Search engine contamination for the present-day search-quality issue.",
    # End Cat 13 — 16 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 14 — Long-Term and Existential Risks (47 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Loss of human control over superintelligence",
        "Misaligned superintelligence",
    ): "Loss of human control specifically for the inability to monitor or constrain even if values were aligned; Misaligned superintelligence specifically when values differ from human ones.",
    (
        "Loss of human control over superintelligence",
        "Recursive self-improvement",
    ): "Loss of human control for the control-failure outcome; Recursive self-improvement specifically for the capability-acceleration mechanism through self-modification.",
    (
        "Loss of human control over superintelligence",
        "Power-seeking AI behavior",
    ): "Loss of human control for the high-level outcome at superintelligence scale; Power-seeking for the specific behavioral mechanism (acquiring resources, influence, capabilities) that may produce it.",
    (
        "Loss of human control over superintelligence",
        "Human disempowerment by AI",
    ): "Loss of human control for the dramatic-rupture framing at superintelligence scale; Human disempowerment for the gradual cumulative framing without superintelligence assumption.",
    (
        "Loss of human control over superintelligence",
        "Loss of human oversight",
    ): "Loss of human control for the long-term framing at superintelligence scale; Loss of human oversight for the present-day inability to inspect or intervene in deployed AI.",
    (
        "Loss of human control over superintelligence",
        "Human extinction scenarios from AI",
    ): "Loss of human control for the control-failure outcome that may or may not lead to extinction; Human extinction scenarios specifically for scenarios where AI causes human extinction.",
    (
        "Recursive self-improvement",
        "Loss of human control over superintelligence",
    ): "Recursive self-improvement specifically for the capability-acceleration mechanism; Loss of human control for the control-failure outcome that may follow.",
    (
        "Recursive self-improvement",
        "Misaligned superintelligence",
    ): "Recursive self-improvement for the capability-acceleration mechanism; Misaligned superintelligence for the values-misalignment outcome that may follow at the resulting capability level.",
    (
        "Recursive self-improvement",
        "Power-seeking AI behavior",
    ): "Recursive self-improvement specifically for the capability-acceleration mechanism through self-modification; Power-seeking for the behavioral pattern of acquiring resources or influence.",
    (
        "Recursive self-improvement",
        "Human disempowerment by AI",
    ): "Recursive self-improvement for the capability-acceleration mechanism; Human disempowerment for the gradual cumulative outcome at societal scale.",
    (
        "Recursive self-improvement",
        "Economic collapse from uncontrolled automation",
    ): "Recursive self-improvement specifically for AI capability acceleration; Economic collapse specifically for labor-market-failure scenarios from automation outpacing absorption.",
    (
        "Power-seeking AI behavior",
        "Misaligned superintelligence",
    ): "Power-seeking for the behavioral pattern of acquiring resources or influence; Misaligned superintelligence for the values-misalignment outcome assuming superintelligence-level capability.",
    (
        "Power-seeking AI behavior",
        "Deceptive alignment",
    ): "Power-seeking for the substantive goal-pursuit (resources, influence); Deceptive alignment for the strategic concealment behavior that may enable it.",
    (
        "Power-seeking AI behavior",
        "Recursive self-improvement",
    ): "Power-seeking for the behavioral pattern of acquiring resources or influence; Recursive self-improvement for the capability-acceleration mechanism.",
    (
        "Power-seeking AI behavior",
        "Loss of human control over superintelligence",
    ): "Power-seeking for the specific behavioral mechanism (acquiring resources, influence); Loss of human control for the high-level outcome at superintelligence scale.",
    (
        "Power-seeking AI behavior",
        "Human disempowerment by AI",
    ): "Power-seeking for the AI-side behavioral mechanism; Human disempowerment for the humans-side outcome of progressively losing consequential decisions.",
    (
        "Power-seeking AI behavior",
        "Economic collapse from uncontrolled automation",
    ): "Power-seeking for the AI-side behavioral mechanism; Economic collapse for the labor-market-failure outcome from automation outpacing absorption.",
    (
        "Misaligned superintelligence",
        "Loss of human control over superintelligence",
    ): "Misaligned superintelligence specifically when values differ from human ones; Loss of human control specifically for the inability to monitor or constrain even if values were aligned.",
    (
        "Misaligned superintelligence",
        "Power-seeking AI behavior",
    ): "Misaligned superintelligence for the values-misalignment outcome at superintelligence scale; Power-seeking for the behavioral pattern of acquiring resources or influence.",
    (
        "Misaligned superintelligence",
        "Recursive self-improvement",
    ): "Misaligned superintelligence for the values-misalignment outcome at superintelligence-level capability; Recursive self-improvement for the capability-acceleration mechanism.",
    (
        "Misaligned superintelligence",
        "Human extinction scenarios from AI",
    ): "Misaligned superintelligence for the values-misalignment outcome; Human extinction scenarios specifically for scenarios where AI causes human extinction, with misalignment as one pathway.",
    (
        "Misaligned superintelligence",
        "Deceptive alignment",
    ): "Misaligned superintelligence as the long-term framing at frontier scale; Deceptive alignment as a present-day capability concern with empirical evals.",
    (
        "Human disempowerment by AI",
        "Loss of human control over superintelligence",
    ): "Human disempowerment for the gradual cumulative framing without superintelligence assumption; Loss of human control for the dramatic-rupture framing at superintelligence scale.",
    (
        "Human disempowerment by AI",
        "Irreversible societal dependence on AI",
    ): "Human disempowerment for the decision-and-capability transfer to AI; Irreversible societal dependence for the inability-to-withdraw outcome at societal scale.",
    (
        "Human disempowerment by AI",
        "Irrecoverable loss of human agency",
    ): "Human disempowerment for the gradual decision-and-capability transfer to AI; Irrecoverable loss of human agency for the cumulative-erosion framing at individual, institutional, and societal levels.",
    (
        "Human disempowerment by AI",
        "Concentration of power in a small elite via AI",
    ): "Human disempowerment for the broader humans-vs-AI decision-transfer framing; Concentration of power specifically for the within-humanity outcome where AI capabilities concentrate in a small elite.",
    (
        "Human disempowerment by AI",
        "Decision dependency on AI",
    ): "Human disempowerment as the long-term framing at societal scale; Decision dependency as a present-day individual phenomenon.",
    (
        "Economic collapse from uncontrolled automation",
        "Job displacement by AI",
    ): "Economic collapse as the long-term framing if automation scale exceeds adaptive capacity; Job displacement as a present-day labor-market phenomenon at sector or occupation scale.",
    (
        "Economic collapse from uncontrolled automation",
        "Concentration of power in a small elite via AI",
    ): "Economic collapse for the labor-market-failure outcome; Concentration of power for the political-economic-dominance outcome of AI capabilities concentrating in a small elite.",
    (
        "Economic collapse from uncontrolled automation",
        "Irreversible societal dependence on AI",
    ): "Economic collapse for the labor-market-failure outcome; Irreversible societal dependence for the inability-to-withdraw outcome at societal scale.",
    (
        "Concentration of power in a small elite via AI",
        "Permanent global authoritarianism via AI",
    ): "Concentration of power in a small elite for the within-humanity power-concentration outcome; Permanent global authoritarianism specifically for the totalitarian global order stable against revolt or reform.",
    (
        "Concentration of power in a small elite via AI",
        "Automation inequality",
    ): "Concentration of power in a small elite as the long-term societal framing including political and structural power; Automation inequality as a present-day economic phenomenon of distributional outcome.",
    (
        "Concentration of power in a small elite via AI",
        "Human disempowerment by AI",
    ): "Concentration of power for the within-humanity outcome where AI capabilities concentrate in a small elite; Human disempowerment for the broader humans-vs-AI decision-transfer framing.",
    (
        "Irreversible societal dependence on AI",
        "Critical dependency on AI systems",
    ): "Irreversible societal dependence on AI as the long-term framing at societal scale where withdrawal is impossible; Critical dependency on AI systems as a present-day organizational phenomenon where fallback is impractical.",
    (
        "Irreversible societal dependence on AI",
        "Human disempowerment by AI",
    ): "Irreversible societal dependence for the inability-to-withdraw outcome at societal scale; Human disempowerment for the gradual decision-and-capability transfer to AI.",
    (
        "Irreversible societal dependence on AI",
        "Irrecoverable loss of human agency",
    ): "Irreversible societal dependence specifically about societal-functions dependency (energy, water, finance); Irrecoverable loss of human agency for the cumulative erosion of agency at individual, institutional, and societal levels.",
    (
        "Irreversible societal dependence on AI",
        "Concentration of power in a small elite via AI",
    ): "Irreversible societal dependence for the inability-to-withdraw framing; Concentration of power specifically for the within-humanity outcome where AI capabilities concentrate in a small elite.",
    (
        "Human extinction scenarios from AI",
        "Misaligned superintelligence",
    ): "Human extinction scenarios specifically for scenarios where AI causes human extinction; Misaligned superintelligence for the values-misalignment outcome that may or may not lead to extinction.",
    (
        "Human extinction scenarios from AI",
        "Loss of human control over superintelligence",
    ): "Human extinction scenarios specifically for scenarios where AI causes human extinction; Loss of human control for the control-failure outcome that may or may not lead to extinction.",
    (
        "Human extinction scenarios from AI",
        "Permanent global authoritarianism via AI",
    ): "Human extinction scenarios specifically for extinction; Permanent global authoritarianism specifically for a stable totalitarian global order — a distinct catastrophic outcome short of extinction.",
    (
        "Human extinction scenarios from AI",
        "Autonomous weapons escalation to catastrophe",
    ): "Human extinction scenarios for the extinction outcome; Autonomous weapons escalation specifically for flash-war scenarios producing catastrophic outcomes at machine speeds.",
    (
        "Human extinction scenarios from AI",
        "Power-seeking AI behavior",
    ): "Human extinction scenarios for the extinction outcome; Power-seeking for the behavioral mechanism that may contribute among other pathways.",
    (
        "Permanent global authoritarianism via AI",
        "Concentration of power in a small elite via AI",
    ): "Permanent global authoritarianism specifically for a totalitarian global order stable against revolt; Concentration of power for the broader within-humanity power-concentration outcome short of stable totalitarianism.",
    (
        "Permanent global authoritarianism via AI",
        "Human extinction scenarios from AI",
    ): "Permanent global authoritarianism specifically for a stable totalitarian global order; Human extinction scenarios specifically for scenarios where AI causes extinction.",
    (
        "Permanent global authoritarianism via AI",
        "Human disempowerment by AI",
    ): "Permanent global authoritarianism specifically for a stable totalitarian outcome with surveillance and autonomous enforcement; Human disempowerment for the broader gradual decision-and-capability transfer to AI.",
    (
        "Autonomous weapons escalation to catastrophe",
        "Escalation due to autonomous systems",
    ): "Autonomous weapons escalation to catastrophe as the long-term framing of system-of-systems flash-war scenarios; Escalation due to autonomous systems as present-day operational risk from autonomous military/security systems.",
    (
        "Irrecoverable loss of human agency",
        "Irreversible societal dependence on AI",
    ): "Irrecoverable loss of human agency for the cumulative erosion of agency at multiple levels; Irreversible societal dependence specifically about societal-functions dependency.",
    (
        "Irrecoverable loss of human agency",
        "Human disempowerment by AI",
    ): "Irrecoverable loss of human agency for the cumulative-erosion framing at individual, institutional, and societal levels; Human disempowerment for the decision-and-capability transfer to AI.",
    (
        "Irrecoverable loss of human agency",
        "Concentration of power in a small elite via AI",
    ): "Irrecoverable loss of human agency for the broad multi-level agency erosion; Concentration of power specifically for the within-humanity outcome where AI capabilities concentrate in a small elite.",
    # End Cat 14 — 47 edges authored
    # ────────────────────────────────────────────────────────────────────────
    # Category 15 — Meta-Risks (Risks About Risk Management) (28 edges)
    # ────────────────────────────────────────────────────────────────────────
    (
        "Safety theater in AI",
        "Underestimating AI risks",
    ): "Safety theater for the performance of safety practices without substantive risk reduction; Underestimating AI risks for the broader systematic underestimation by decision-makers.",
    (
        "Safety theater in AI",
        "Misleading AI benchmarks",
    ): "Safety theater for safety-practice performances broadly; Misleading AI benchmarks specifically when capability benchmarks fail to predict real-world performance or are gamed.",
    (
        "Underestimating AI risks",
        "Safety theater in AI",
    ): "Underestimating AI risks for the systematic-underestimation issue by decision-makers; Safety theater specifically for the performance of safety practices without substantive risk reduction.",
    (
        "Underestimating AI risks",
        "Overestimating AI capabilities",
    ): "Underestimating AI risks for the risk-side underestimation by decision-makers; Overestimating AI capabilities for the capabilities-side overestimation by organizations and individuals.",
    (
        "Underestimating AI risks",
        "Public misunderstanding of AI",
    ): "Underestimating AI risks specifically for decision-maker underestimation of risks; Public misunderstanding for the broader category of incomplete or inaccurate public mental models of AI.",
    (
        "Overregulation stifling beneficial AI innovation",
        "Fragmented AI standards",
    ): "Overregulation specifically when restrictive regulation suppresses beneficial innovation; Fragmented AI standards for the multiple-standards-regimes complexity issue regardless of restrictiveness.",
    (
        "Overregulation stifling beneficial AI innovation",
        "Regulatory lag for AI",
    ): "Overregulation for the too-restrictive outcome; Regulatory lag for the opposite issue of capabilities evolving faster than rules can keep up.",
    (
        "Overregulation stifling beneficial AI innovation",
        "Panic or moral hysteria about AI",
    ): "Overregulation specifically for the restrictive-regulation outcome; Panic or moral hysteria for the upstream attitudinal driver that may produce it among other policy outcomes.",
    (
        "Regulatory lag for AI",
        "Fragmented AI standards",
    ): "Regulatory lag specifically when rules cannot keep up with capability evolution; Fragmented AI standards for the multiple-standards-regimes complexity issue.",
    (
        "Regulatory lag for AI",
        "Competitive pressure reducing AI safety standards",
    ): "Regulatory lag for the regulator-side issue of rules lagging capabilities; Competitive pressure for the industry-side issue of labs racing past their own safety review.",
    (
        "International AI prisoner's dilemma",
        "Competitive pressure reducing AI safety standards",
    ): "International AI prisoner's dilemma specifically for state-level race-to-the-bottom dynamics; Competitive pressure for the lab-level race-to-the-bottom dynamics between AI companies.",
    (
        "Competitive pressure reducing AI safety standards",
        "International AI prisoner's dilemma",
    ): "Competitive pressure for the lab-level race-to-the-bottom dynamics between AI companies; International AI prisoner's dilemma specifically for the state-level race-to-the-bottom dynamics.",
    (
        "Competitive pressure reducing AI safety standards",
        "Safety theater in AI",
    ): "Competitive pressure for the underlying race-to-the-bottom dynamic causing safety shortcuts; Safety theater for the visible-performance-without-substance outcome that may result.",
    (
        "Competitive pressure reducing AI safety standards",
        "Underestimating AI risks",
    ): "Competitive pressure for the structural-incentive cause; Underestimating AI risks for the cognitive cause where decision-makers themselves underestimate risks.",
    (
        "Fragmented AI standards",
        "Regulatory lag for AI",
    ): "Fragmented AI standards specifically for the multiple-standards-regimes complexity issue; Regulatory lag specifically when rules cannot keep up with capability evolution.",
    (
        "Public misunderstanding of AI",
        "AI hype cycles",
    ): "Public misunderstanding for the broader category of inaccurate public mental models; AI hype cycles specifically for the inflated-expectations-then-disillusionment dynamic in media and discourse.",
    (
        "Public misunderstanding of AI",
        "Lack of internal AI expertise",
    ): "Public misunderstanding for the broader category of inaccurate public mental models of AI; Lack of internal AI expertise specifically when organizations lack technical, ethical, or governance expertise.",
    (
        "Public misunderstanding of AI",
        "Underestimating AI risks",
    ): "Public misunderstanding for the broader category of incomplete or inaccurate public mental models; Underestimating AI risks specifically for decision-maker underestimation.",
    (
        "AI hype cycles",
        "Panic or moral hysteria about AI",
    ): "AI hype cycles for the inflated-expectations-then-disillusionment dynamic; Panic or moral hysteria specifically for disproportionate fear or moral panic about AI.",
    (
        "AI hype cycles",
        "Public misunderstanding of AI",
    ): "AI hype cycles specifically for the inflated-expectations-then-disillusionment dynamic in media and discourse; Public misunderstanding for the broader category of inaccurate public mental models.",
    (
        "AI hype cycles",
        "Competitive pressure reducing AI safety standards",
    ): "AI hype cycles for the attitudinal-dynamic framing; Competitive pressure for the structural-incentive framing of race-to-the-bottom dynamics that hype may feed.",
    (
        "Panic or moral hysteria about AI",
        "AI hype cycles",
    ): "Panic or moral hysteria specifically for disproportionate fear about AI; AI hype cycles for the broader inflated-expectations-then-disillusionment dynamic in both fear and excitement directions.",
    (
        "Panic or moral hysteria about AI",
        "Overregulation stifling beneficial AI innovation",
    ): "Panic or moral hysteria for the attitudinal driver; Overregulation for the restrictive-regulation policy outcome that may follow among other outcomes.",
    (
        "Panic or moral hysteria about AI",
        "Public misunderstanding of AI",
    ): "Panic or moral hysteria specifically for disproportionate fear about AI; Public misunderstanding for the broader category of inaccurate public mental models.",
    (
        "Panic or moral hysteria about AI",
        "Underestimating AI risks",
    ): "Panic or moral hysteria for disproportionate fear about AI; Underestimating AI risks for the opposite issue of decision-makers systematically underestimating risks.",
    (
        "Misleading AI benchmarks",
        "Safety theater in AI",
    ): "Misleading AI benchmarks specifically when capability benchmarks fail to predict real-world performance or are gamed; Safety theater for the broader performance of safety practices without substantive risk reduction.",
    (
        "Misleading AI benchmarks",
        "AI hype cycles",
    ): "Misleading AI benchmarks specifically for the benchmark-validity issue; AI hype cycles for the broader inflated-expectations dynamic that misleading benchmarks may feed.",
    (
        "Misleading AI benchmarks",
        "Underestimating AI risks",
    ): "Misleading AI benchmarks for the benchmark-validity issue; Underestimating AI risks for the systematic-underestimation issue by decision-makers across multiple inputs.",
    # End Cat 15 — 28 edges authored — Pass B authoring COMPLETE
}

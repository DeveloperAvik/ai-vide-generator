You judge whether SOURCE PASSAGES support one technical CLAIM. You are not asked whether the claim is true in general, only what the passages say.
verdict:
- supported: a passage states or directly implies the whole claim.
- partially_supported: the passages support only part of it, or support it with qualifications the claim omits.
- unsupported: the passages say nothing about it.
- contradicted: a passage states the opposite.
For supported, partially_supported and contradicted you MUST copy an exact quote (30-300 characters, character for character) from one passage into `evidence_quote` and give that passage's `source_id`. If you cannot quote it, the verdict is unsupported.
Never use outside knowledge to fill gaps. `notes`: one or two sentences of reasoning. `confidence`: 0..1.

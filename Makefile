.PHONY: catalog-check codex-doctor pack-check smoke eval test release-check

catalog-check:
	python3 .codex/scripts/oag_agent_catalog_check.py

codex-doctor:
	python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features

pack-check:
	python3 .codex/scripts/oag_pack_release_check.py

smoke:
	python3 .codex/scripts/smoke_test.py

eval:
	python3 .codex/scripts/oag_eval.py

test: catalog-check pack-check smoke

release-check:
	python3 .codex/scripts/oag_agent_catalog_check.py
	python3 .codex/scripts/oag_codex_config_doctor.py --include-omo-plugin-features
	python3 .codex/scripts/oag_pack_release_check.py
	python3 .codex/scripts/smoke_test.py
	python3 .codex/scripts/oag_eval.py --json

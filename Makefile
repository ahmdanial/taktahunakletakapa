.PHONY: help setup run attack submit once stats teams recon demo clean
CONFIG ?= config/config.yaml

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	 | awk 'BEGIN{FS=":.*?## "}{printf "  %-10s %s\n", $$1, $$2}'

setup:  ## install deps and create config from the sample
	pip install -r requirements.txt
	@test -f $(CONFIG) || cp config/config.sample.yaml $(CONFIG)
	@chmod +x exploits/* attack/*.sh defense/*.sh 2>/dev/null || true
	@echo "edit $(CONFIG), then: make run"

run:     ## run the full farm (attack + submit)
	python3 -m farm run -c $(CONFIG)
attack:  ## run only the attack loop
	python3 -m farm attack -c $(CONFIG)
submit:  ## run only the submit loop
	python3 -m farm submit -c $(CONFIG)
once:    ## one attack round + one submit round, then exit
	python3 -m farm once -c $(CONFIG)
stats:   ## print flag-queue counts
	python3 -m farm stats -c $(CONFIG)
teams:   ## print expanded target list
	python3 -m farm teams -c $(CONFIG)
recon:   ## scan services across all targets
	./attack/recon.sh -c $(CONFIG)

demo:    ## end-to-end self-test against local mocks (no real CTF needed)
	./test/demo.sh

clean:   ## remove local state
	rm -f farm.db farm.db-wal farm.db-shm
	rm -rf pcaps .backups __pycache__ farm/__pycache__

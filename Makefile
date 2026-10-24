APP       := build/ContextAgent.app
BUNDLE_ID := com.sehajpreet.contextagent
# A real signing identity keeps the Accessibility grant across rebuilds; "-" (ad-hoc) loses it each time.
IDENTITY  ?= $(shell security find-identity -v -p codesigning | awk -F'"' '/Apple Development/ {print $$2; exit}')
SIGN_AS   := $(if $(IDENTITY),$(IDENTITY),-)

.PHONY: app run-app brain test dump reset-permission

app: ## Build the menu-bar app and wrap it in a signed .app bundle
	cd app && swift build -c release
	rm -rf $(APP) && mkdir -p $(APP)/Contents/MacOS
	cp app/.build/release/ContextAgent $(APP)/Contents/MacOS/ContextAgent
	cp app/Info.plist $(APP)/Contents/Info.plist
	codesign --force --sign "$(SIGN_AS)" --identifier $(BUNDLE_ID) $(APP)
	@echo "Signed with: $(SIGN_AS)"

run-app: app ## Build and launch
	-pkill -x ContextAgent
	open $(APP)

brain: ## Run the brain API on 127.0.0.1:8765
	cd brain && uv run brain serve

test: ## Brain and app unit tests
	cd brain && uv run pytest -q
	cd app && swift test

dump: ## Read one app's window once and print it: make dump BUNDLE=com.google.Chrome
	@test -n "$(BUNDLE)" || (echo "usage: make dump BUNDLE=com.google.Chrome" && exit 1)
	open -n -W $(APP) --args --dump $(BUNDLE) --out $(CURDIR)/build/dump.json
	@cat build/dump.json; echo

reset-permission: ## Forget the Accessibility grant (needed after an ad-hoc re-sign)
	tccutil reset Accessibility $(BUNDLE_ID)

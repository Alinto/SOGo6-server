
.PHONY: docs clean

DOCS_SRC := docs
DOCS_OUTPUT := build/docs

docs:
	@echo "Building AsciiDoc -> HTML..."
	@mkdir -p $(DOCS_OUTPUT)
	@asciidoctor -D $(DOCS_OUTPUT) $(DOCS_SRC)/index.adoc
	@echo "HTML built in $(DOCS_OUTPUT)"

clean:
	@echo "Cleaning..."
	@rm -rf $(DOCS_OUTPUT)
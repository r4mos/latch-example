all: pack

pack:
	zip --quiet --recurse-paths latch-example latch_example/ -i '*.py'
	zip --quiet --junk-paths latch-example latch_example/__main__.py
	echo '#!/usr/bin/env python' > latch-example
	cat latch-example.zip >> latch-example
	rm latch-example.zip
	chmod a+x latch-example
	mv latch-example bin/latch-example

clean:
	rm -f bin/latch-example

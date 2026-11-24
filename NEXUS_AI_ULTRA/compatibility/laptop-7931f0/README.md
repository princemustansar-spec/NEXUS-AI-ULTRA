# Reviewed laptop app baseline

baseline_app.py is the source supplied by the user after the installer refused
an unrecognized app.py. Its SHA-256 is
7931f0dbef329bcddc925547e1a30a47915fb9d9aaae26640bf1dde2f9a05e1d.

app.py is a conflict-free three-way merge of that file with the tested Hermes
integration, using b630568caa735e756f96b22db07a354f041db88b as the common base.
It preserves saved/new chat session APIs, the active-chat guard, voice settings
and all controllers outside the reviewed chat/lifespan/safety integration.

The package selects this variant only when the installed app exactly matches
the supplied baseline. It does not replace the user's session-store, voice,
account-provider or GUI implementation files. No credential literals were found
in the supplied source before publication. The user's private project notes
were not supplied or published; the installer appends a separate local note.

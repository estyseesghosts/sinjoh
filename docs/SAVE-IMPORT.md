# Importing emulator saves

Place the save in `sdmc:/3ds/sinjoh/saves/platinum.sav`. Raw 512 KiB cartridge
images load directly. A DeSmuME `.dsv` with a 512 KiB payload and version-zero
footer, or a No$GBA `.SAV` with a 512 KiB payload (uncompressed or packed),
is recognized by its content and converted on first load. Rename a copy to `platinum.sav`;
Sinjoh does not look for alternate file names.

There is one length ambiguity: a packed No$GBA file can itself be exactly
512 KiB. Sinjoh treats every file of that length as a raw image, so export such
a file to raw format before use. The importer cannot distinguish it solely by
length; interpreting matching bytes in a raw image as a container would change
the existing raw-save behavior.

The importer validates the container's header, sizes and, for packed No$GBA,
every run and the terminator. Unsupported, malformed or truncated inputs are
rejected; they are never interpreted as blank saves. The converter writes and
verifies a complete original copy as `platinum.sav.orig` (or `.orig.1`,
`.orig.2`, etc. if the name is occupied), then writes, flushes and verifies a
temporary raw image before replacing the active path. Existing backups are
never overwritten. Successful conversion is one-time: the active file is then
a raw image, and the original remains alongside it.

If storage is full, read-only, or an operation fails, conversion stops and the
log reports failure. The original remains either at `platinum.sav` or in the
verified `.orig` backup. A temporary or incomplete backup can also remain; do
not assume every backup is complete. If an interruption leaves the active file
missing but a backup or temporary file exists, Sinjoh refuses to create a blank
save. Restore a known complete original to `platinum.sav` and retry. In particular, the 3DS
filesystem does not guarantee an atomic replace: the backup is the recovery
copy, not a guarantee that the rename survives power loss.

Container references: DeSmuME's
[`mc.cpp`](https://github.com/TASEmulators/desmume/blob/master/desmume/src/mc.cpp)
defines the footer, No$GBA header and packed data fields; Kohjoh's
`src/compat/nitro/src/port_card.c` was exercised with actual exports. File
flushing and rename behavior are documented in Coffeepot's
`ctr/engineering/filesystem-and-saves.md`. This implementation still needs
Platinum Continue/save/reload checks with real exports and 3DS hardware testing.

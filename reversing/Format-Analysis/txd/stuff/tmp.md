

to find file name
00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 ** ** FileName, where ** is any byte
end of file name indicated by 00 00 00 00

start of image data at the first non 00 byte after the name
end of image data indicated by (03 00 00 00), start of next image block (14 00 00 00)

.txd texture dictionary format containing a grouping of image file blocks
it starts with image data imediatly no txd headers just blocks of images

the txd file starts with 16 00 00 00
(2D 00 02 1C) is a common indicator with no singular purpose


hex within () indicate constants that have been the same accross many file
all hex values here were extracted directly

Start of image


found to be `00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 ** ** FileName`, end of file name is not indicated explicitly but always has a long list of 00 hex before the start of the its assosiated image data
16 00 00 00 84 FE 01 00 (2D 00 02 1C) {(01 00 00 00) {04 00 00 00}} (2D 00 02 1C) 09 00 0A 00 (15 00 00 00) 08 01 00 00 (2D 00 02 1C) (01 00 00 00) DC 00 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 33 02 (filename)-- this is the first file in the txd and there are no bytes before the name here
16 00 00 00 D0 10 04 00 (2D 00 02 1C) {(01 00 00 00) {04 00 00 00}} (2D 00 02 1C) 0F 00 0A 00 (15 00 00 00) 08 01 00 00 (2D 00 02 1C) (01 00 00 00) DC 00 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 33 02 (filename)-- this is the first file in the txd and there are no bytes before the name here

 XX  00 00 00  XX   XX   XX   XX   XX   XX   XX   XX   XX  00 00 00  XX  00  XX   XX   XX   XX  XX    XX   XX   XX   XX   XX  (15 00 00 00)  XX   XX  00 00 (2D 00 02 1C) (01 00 00 00)  XX   XX  00 00 (2D 00 02 1C) (00 00 00 0A) 00 00  XX   XX  (filename)
*14* 00 00 00 *2D* *00* *02* *1C* *2F* *EA* *00* *00* *08* 00 00 00 *2D* 00 *02* *1C* *2F* *F6* *B5* *38* *E2* *3D* *DC* *82* (15 00 00 00) *94* *55* 00 00 (2D 00 02 1C) (01 00 00 00) *68* *55* 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 *11* *06*
*14* 00 00 00 *2D* *00* *02* *1C* *2F* *EA* *00* *00* *08* 00 00 00 *2D* 00 *02* *1C* *03* *69* *0D* *A0* *4B* *CB* *F1* *95* (15 00 00 00) *18* *AB* 00 00 (2D 00 02 1C) (01 00 00 00) *EC* *AA* 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 *11* *06*

entire image
(16 00 00 00) D0 10 04 00 (2D 00 02 1C) {(01 00 00 00) {04 00 00 00}} (2D 00 02 1C) 0F 00 0A 00 (15 00 00 00) 08 01 00 00 (2D 00 02 1C) (01 00 00 00) DC 00 00 00 (2D 00 02 1C) (00 00 00 0A)( 00 00 33 02) [[73 71 75 61 72 65] || (filename) ] 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 00 1A 20 01 52 00 10 00 10 20 01 04 08 80 00 00 00 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB 5D EF 5C E7 EA AE BA AB (03 00 00 00)
(16 00 00 00) A8 E9 05 00 (2D 00 02 1C) {(01 00 00 00) {04 00 00 00}} (2D 00 02 1C) 28 00 0A 00 (15 00 00 00) 88 04 00 00 (2D 00 02 1C) (01 00 00 00) 5C 04 00 00 (2D 00 02 1C) (00 00 00 0A) (00 00 11 02) [[62 75 62 62 6C 65 5F 30 31] || (filename) ] 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 03 00 1A 20 01 53 00 20 00 20 10 01 04 09 00 04 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 10 00 92 FF FF FF FF 00 00 00 00 00 00 20 85 A5 AB AC 78 FF FF FF FF 00 00 00 00 32 55 BA BB 89 87 66 56 FF FF FF FF 00 00 00 00 45 13 BB 9B 87 98 66 66 FF FF FF FF 00 00 00 00 00 00 47 01 BA 49 87 B9 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 17 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 20 00 91 FF FF FF FF 00 00 00 00 30 BA B3 7A AA 67 7B 56 FF FF FF FF 00 00 00 00 68 66 66 45 45 34 44 23 FF FF FF FF 00 00 00 00 55 54 34 34 33 22 12 12 FF FF FF FF 00 00 00 00 54 55 33 44 32 43 21 62 FF FF FF FF 00 00 00 00 66 86 65 66 87 67 EB 69 FF FF FF FF 00 00 00 00 9A 02 A7 28 76 8A 65 A7 FF FF FF FF 00 00 00 00 00 00 00 00 01 00 06 00 FF FF FF FF 00 00 00 00 00 C5 20 AA 50 8B 80 7A FF FF FF FF 00 00 00 00 68 45 66 44 56 34 45 23 FF FF FF FF 00 00 00 00 33 12 23 11 12 01 12 00 FF FF FF FF 00 00 00 00 11 01 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 10 62 00 41 00 10 00 00 FF FF FF FF 00 00 00 00 FC 6A 98 46 33 33 10 21 FF FF FF FF 00 00 00 00 55 86 44 66 43 65 32 54 FF FF FF FF 00 00 00 00 3A 00 7A 01 A8 03 A7 05 FF FF FF FF 00 00 00 00 A2 69 B3 68 B5 58 B5 67 FF FF FF FF 00 00 00 00 45 23 35 13 35 22 34 12 FF FF FF FF 00 00 00 00 01 00 01 00 01 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 10 00 10 00 10 00 10 FF FF FF FF 00 00 00 00 32 54 22 54 21 53 22 43 FF FF FF FF 00 00 00 00 96 08 86 29 86 2A 85 3A FF FF FF FF 00 00 00 00 B5 67 B4 68 A3 68 A1 69 FF FF FF FF 00 00 00 00 34 22 35 13 35 13 45 23 FF FF FF FF 00 00 00 00 01 00 00 00 01 00 11 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 10 00 10 00 10 FF FF FF FF 00 00 00 00 21 53 22 44 22 54 32 54 FF FF FF FF 00 00 00 00 76 3A 86 39 86 19 96 07 FF FF FF FF 00 00 00 00 70 7A 40 8B 10 99 00 B4 FF FF FF FF 00 00 00 00 45 23 56 34 57 35 68 45 FF FF FF FF 00 00 00 00 12 00 12 11 23 21 33 22 FF FF FF FF 00 00 00 00 00 00 13 00 28 00 12 01 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 10 11 FF FF FF FF 00 00 00 00 00 21 10 21 11 32 22 33 FF FF FF FF 00 00 00 00 32 64 43 65 53 75 54 86 FF FF FF FF 00 00 00 00 A7 05 98 02 79 00 29 00 FF FF FF FF 00 00 00 00 00 70 00 10 00 00 00 00 FF FF FF FF 00 00 00 00 7A 56 A9 67 82 7A 20 A8 FF FF FF FF 00 00 00 00 44 23 45 34 66 45 68 56 FF FF FF FF 00 00 00 00 22 11 23 23 34 33 55 45 FF FF FF FF 00 00 00 00 21 21 22 33 43 43 54 55 FF FF FF FF 00 00 00 00 32 43 43 55 54 65 66 87 FF FF FF FF 00 00 00 00 65 A7 76 69 A7 17 6A 01 FF FF FF FF 00 00 00 00 05 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 61 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 AA 78 73 AA 10 62 00 00 FF FF FF FF 00 00 00 00 66 56 89 88 98 9A 10 33 FF FF FF FF 00 00 00 00 56 66 87 98 AA 79 23 01 FF FF FF FF 00 00 00 00 87 99 9A 27 25 00 00 00 FF FF FF FF 00 00 00 00 05 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 00 00 00 00 00 00 00 00 FF FF FF FF 00 00 00 00 (03 00 00 00)


(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 2E 16 68 B0 85 AA 8A FA (15 00 00 00) 88 10 00 00 (2D 00 02 1C) (01 00 00 00) 5C 10 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 02 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) AF 7E 95 04 8B B0 36 3A (15 00 00 00) 94 55 00 00 (2D 00 02 1C) (01 00 00 00) 68 55 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 02 69 3B CB 8B E2 34 40 (15 00 00 00) 18 AB 00 00 (2D 00 02 1C) (01 00 00 00) EC AA 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 07 C5 E2 F5 91 3E DB 6A (15 00 00 00) 18 AB 00 00 (2D 00 02 1C) (01 00 00 00) EC AA 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 65 19 02 5D 06 36 8F 93 (15 00 00 00) 8C 05 00 00 (2D 00 02 1C) (01 00 00 00) 60 05 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) F8 72 CB 94 BA 82 01 DE (15 00 00 00) 88 00 01 00 (2D 00 02 1C) (01 00 00 00) 5C 00 01 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 02 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) AF 7E 95 04 8B B0 36 3A (15 00 00 00) 94 55 00 00 (2D 00 02 1C) (01 00 00 00) 68 55 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 63 FD 85 64 3A 09 C0 AE (15 00 00 00) 94 55 00 00 (2D 00 02 1C) (01 00 00 00) 68 55 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 43 1E 39 82 E4 3B C6 B8 (15 00 00 00) 90 15 00 00 (2D 00 02 1C) (01 00 00 00) 64 15 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 4A 49 7C FD B6 07 CF 33 (15 00 00 00) 90 15 00 00 (2D 00 02 1C) (01 00 00 00) 64 15 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) D9 D1 A8 86 7A EF 35 BC (15 00 00 00) 88 10 00 00 (2D 00 02 1C) (01 00 00 00) 5C 10 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 02 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) AC F0 F4 8A 4E 0E 81 C0 (15 00 00 00) 10 0B 00 00 (2D 00 02 1C) (01 00 00 00) E4 0A 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)
(14 00 00 00) (2D 00 02 1C) (2F EA 00 00) (08 00 00 00) (2D 00 02 1C) 65 19 02 5D 06 36 8F 93 (15 00 00 00) 8C 0A 00 00 (2D 00 02 1C) (01 00 00 00) 60 0A 00 00 (2D 00 02 1C) (00 00 00 0A) 00 00 11 06 (filename)

hex between end of name and start of image data, these snipits may partially overlap with image data
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 83 00 1A 20 01 53 00 20 00 20 10 02 04 09 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 02 00 1A 20 01 52 00 10
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 83 00 1A 20 01 53 00 20 00 20 10 02 04 09 00 04 00 00 00 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 83 00 1A 20 01 53 00 20 00 20 10 02 04 09 00 04 00 00 00 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 28 00 01 02 00 40 00 40
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 00 00 83 00 1A 20 01 53 00 40 00 40 10
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 00 00 83 00 1A 20 01 53 00 40 00 40 10
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 83 00 1A 20 01 53 00 40 00 40 10 03 04 09 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 83 00 1A 20 01 53 00 80 00 80 10 04 04 09 00 40
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 83 00 1A 20 01 53 00 80 00 80 10 04 04 09 00 40 00 00 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 83 00 1A 20 01 53 00 80 00 80 10 04 04 09 00 40 00 00
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 82 00 1A 20 01 52 01 00 01 00 20 05 04
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 00 00 00 00 00 00 82 00 1A 20 01 52 01 00 01 00 20 05 04
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 82 00 1A 20 01 52 01 00 01 00 20 05 04 08 00 80 00 00 1E F8 1D F8
(filename) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) (00 00 00 00) 00 00 00 00 00 82 00 1A 20 01 52 01 00 01 00 20 05 04 08 00 80 00 00 1E




Searching for .txd files in and below: a:\Dev\Games\TheSimpsonsGame\PAL\test

Processing file: a:\Dev\Games\TheSimpsonsGame\PAL\test\in\dayspringfieldstoodstill_global.txd
File starts with TXD_MAGIC.

[1] square at hex 16 (offset 0x0)
[2] ember1 at hex 14 (offset 0x114)
[3] shine1 at hex 14 (offset 0xBAC)
[4] ribbon01 at hex 14 (offset 0x16C8)
[5] fakeshdw at hex 14 (offset 0x275C)
[6] ribbn_mask at hex 14 (offset 0x37F0)
[7] smoke1 at hex 14 (offset 0x4884)
[8] fire64bw at hex 14 (offset 0x5E20)
[9] hittarget at hex 14 (offset 0x73BC)
[10] smoke2 at hex 14 (offset 0x8958)
[11] hud_targetlock at hex 14 (offset 0xC9EC)
[12] blast03 at hex 14 (offset 0x11F8C)
[13] toon_smk_01 at hex 14 (offset 0x12FDB)
[14] blast_mark at hex 14 (offset 0x1CACC)
[15] shards2 at hex 14 (offset 0x2206C)
[16] fireb002 at hex 14 (offset 0x2760C)
[17] dome at hex 14 (offset 0x2CBAC)
[18] rokc at hex 14 (offset 0x34C40)
[19] smoke004 at hex 14 (offset 0x3CCD4)
[20] anim_ray1 at hex 14 (offset 0x44078)
[21] Arcs at hex 14 (offset 0x57808)
[22] scrollfire02 at hex 14 (offset 0x6789C)
[23] shards1 at hex 14 (offset 0x7CD3C)
[24] uvsmoke1 at hex 14 (offset 0x922E0)

Processing file: a:\Dev\Games\TheSimpsonsGame\PAL\test\in\frontend_global.txd
File starts with TXD_MAGIC.

[1] square at hex 16 (offset 0x0)
[2] hud_target_center at hex 14 (offset 0x114)
[3] target_railshooter at hex 14 (offset 0x6AC)
[4] targeting_nontarget at hex 14 (offset 0xC44)
[5] fakeshdw at hex 14 (offset 0x11DC)
[6] hittarget at hex 14 (offset 0x2270)
[7] healthbar at hex 14 (offset 0x380C)
[8] targeting_f2f at hex 14 (offset 0x4DA8)
[9] hud_targetlock at hex 14 (offset 0x6344)
[10] targeting_firearm at hex 14 (offset 0xB8E4)
[11] hud_targetlock02 at hex 14 (offset 0xFCBC)
[12] projtex_hog at hex 14 (offset 0x16424)
[13] projtex_sax at hex 14 (offset 0x20F48)
[14] texture_not_specified at hex 14 (offset 0x2BA6C)
[15] texture_not_found at hex 14 (offset 0x36590)

Processing file: a:\Dev\Games\TheSimpsonsGame\PAL\test\in\loc_global.txd
File starts with TXD_MAGIC.

[1] square at hex 16 (offset 0x0)
[2] ember1 at hex 14 (offset 0x114)
[3] shine1 at hex 14 (offset 0xBAC)
[4] fakeshdw at hex 14 (offset 0x16C8)
[5] smoke1 at hex 14 (offset 0x275C)
[6] hittarget at hex 14 (offset 0x3CF8)
[7] hud_targetlock at hex 14 (offset 0x5294)
[8] toon_smk_01 at hex 14 (offset 0xA834)
[9] Arcs at hex 14 (offset 0xFDD4)



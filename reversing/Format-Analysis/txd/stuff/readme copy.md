
when reading file

start of file

first 4 Bytes - 16000000

next 4 Bytes - Varies

next 4 Bytes - 2d00021c

next 4 Bytes - 01000000

next 4 Bytes - 04000000


next 4 Bytes - 2d00021c

next 4 Bytes - First 2 Varied but all end with 00 0a 00


next 4 Bytes - 15000000


next 4 Bytes Varies but ends with 00


next 4 - 2d00021c

next 4 - 01000000


next 4 Bytes Varies but ends with 00


next 4 - 2d00021c

next 4 - 0000000a


next 4 - one of these three 00001102 - 00001106 - 00003302


next 66 Bytes - this is the section containing file names for the textures


next 5 Bytes- one of these 0000182801 - 01001a2001 - 02001a2001 - 03001a2001 - 8000182801 - 8000280001 - 81001a2001 - 82001a2001 - 83001a2001


next 1 byte - this is one of the 5 file format identifiers, 02 - 52 - 53 - 54 - 86


next 12-bytes - contains the meta data about the image data


all following bytes upto 03 00 00 00 end marker and 14 00 00 00 start of next image marker


where 14 00 00 00 is exactly like 16 00 00 00 but for all subsequent images

For all images after the first

first 20 Bytes - 140000002d00021c2fea0000080000002d00021c

next 8 - Varied

next 4 - 15000000

next 4 - varied but all end with 00

next 4 - 2d00021c

next 4 - 01000000

next 4 - varied but all end with 00

next 4 - 2d00021c

next 4 - 0000000a

next 4 - one of these four 00001102 - 00001106 - 00003302 - 00003306

next 66 - file names

next 5 - one of these 0000182801 - 0000280001 - 01001a2001 - 02001a2001 - 03001a2001 - 8000182801 - 8000280001 - 81001a2001 - 82001a2001 - 83001a2001

next 1 byte - this is one of the 5 file format identifiers, 02 - 52 - 53 - 54 - 86

next 12-bytes - contains the meta data about the image data

all following bytes upto 03 00 00 00 end marker and 14 00 00 00 start of next image marker

the end of file is not explicitly indicated

a 03 00 00 00 14 00 00 00 marker is present indicating another image but ends just before file name 

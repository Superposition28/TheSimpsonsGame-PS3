from inc_noesis import *

def registerNoesisTypes():
    handle = noesis.register("The Simpsons game [PS3]", ".txd")
    noesis.setHandlerTypeCheck(handle, noepyCheckType)
    noesis.setHandlerLoadRGBA(handle, noepyLoadRGBA)
    #noesis.logPopup()
    return 1

def noepyCheckType(data):
    bs = NoeBitStream(data)
    if bs.readUInt() != 0x16: return 0
    return 1
    
def noepyLoadRGBA(data, texList):
    rapi.processCommands("-texnorepfn")
    bs = NoeBitStream(data)
    bs.seek(0x28)         
    this = 1
    while True:
        bs.seek(0x14, 1)
        texName = noeStrFromBytes(bs.readBytes(16))
        print(this, "-", texName)
        this += 1
        bs.seek(0x37, 1)
        #print(hex(bs.tell()), ":here")
        imgFmt = bs.readUByte()
        bs.setEndian(NOE_BIGENDIAN)
        imgWidth = bs.readUShort()
        imgHeight = bs.readUShort()
        bs.readByte()
        numMips = bs.readUByte()
        bs.readByte()
        bs.readByte()
        print(imgWidth, "x", imgHeight, "-", hex(imgFmt), "\n")
        bs.setEndian(NOE_LITTLEENDIAN)
        for i in range(numMips):
            mipSize = bs.readUInt()
            data = bs.readBytes(mipSize)
            #DXT1
            if imgFmt == 0x52:
                texFmt = noesis.NOESISTEX_DXT1
            #DXT3
            elif imgFmt == 0x53:
                texFmt = noesis.NOESISTEX_DXT3
            #DXT5
            elif imgFmt == 0x54:
                texFmt = noesis.NOESISTEX_DXT5
            #morton order swizzled raw 
            elif imgFmt == 0x86:
                untwid = bytearray()
                for x in range(imgWidth):
                    for y in range(imgHeight):
                        idx = noesis.morton2D(x, y)
                        untwid += data[idx * 4:idx * 4 + 4]
                data = rapi.imageDecodeRaw(untwid, imgWidth, imgHeight, "b8g8r8a8")
                texFmt = noesis.NOESISTEX_RGBA32
            #morton order swizzled raw ??? 
            elif imgFmt == 0x2: 
                untwid = bytearray()
                for x in range(imgWidth):
                    for y in range(imgHeight):
                        idx = noesis.morton2D(x, y)
                        untwid += data[idx * 2:idx * 2 + 2]
                data = rapi.imageDecodeRaw(untwid, imgWidth, imgHeight, "p8a8")
                texFmt = noesis.NOESISTEX_RGBA32
            if i == 0:
                texList.append(NoeTexture(texName, imgWidth, imgHeight, data, texFmt))
        bs.seek(0x2c, 1)
        if bs.tell() == bs.getSize():
            break
    return 1
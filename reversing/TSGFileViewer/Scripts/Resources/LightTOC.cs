using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace Assets.Scripts.Resources
{
    [Serializable]
    public class LightTOC : Resource
    {
	    public ushort magicNumber;
	    public ushort version;

	    public LightConstructParams[] LightArr;

	    public LightTOC(byte[] data)
	    {
		    var stream = new MemoryStream(data);
		    var reader = new BinaryReader(stream);

			magicNumber = reader.ReadUInt16();
			version = reader.ReadUInt16();

			var pLightArr = reader.ReadUInt32BigEndian();
			var pBoxLightArr = reader.ReadUInt32BigEndian();
			var nLights = reader.ReadUInt16BigEndian();
			var nBoxLights = reader.ReadUInt16BigEndian();

			LightArr = new LightConstructParams[nLights];
			if (nLights != 0)
			{
				reader.BaseStream.Position = pLightArr;
				for (var i = 0; i < nLights; i++)
				{
					LightArr[i] = new LightConstructParams(reader);
				}
			}
			
			if (nBoxLights != 0)
			{
				reader.BaseStream.Position = pBoxLightArr;

				throw new NotImplementedException();
			}

			reader.Dispose();
		    stream.Dispose();
		}
    }

    [Serializable]
    public class LightConstructParams
    {
	    public Guid128 guid;
	    public RwMatrixTag matrix;
	    public byte rwLightType;
	    public byte rwLightFlags;
	    public byte insideOutside;
	    public byte pad0;
	    public float diffuseAmbient;
	    public Color32 color;
	    public float intensity;
	    public float radius;
	    public float fullBrightRadius;
	    public float coneAngle;
	    public float fullBrightAngle;

	    public LightConstructParams(BinaryReader reader)
	    {
		    guid = new Guid128(reader);
		    matrix = new RwMatrixTag(reader);
		    rwLightType = reader.ReadByte();
			rwLightFlags = reader.ReadByte();
			insideOutside = reader.ReadByte();
			pad0 = reader.ReadByte();
			diffuseAmbient = reader.ReadSingleBigEndian();
			color = new Color32(reader.ReadByte(), reader.ReadByte(), reader.ReadByte(), reader.ReadByte());
			intensity = reader.ReadSingleBigEndian();
			radius = reader.ReadSingleBigEndian();
			fullBrightRadius = reader.ReadSingleBigEndian();
			coneAngle = reader.ReadSingleBigEndian();
			fullBrightAngle = reader.ReadSingleBigEndian();
	    }
    }
}

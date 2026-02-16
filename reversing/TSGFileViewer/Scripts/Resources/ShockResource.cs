using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Assets.Scripts.Resources
{
    /// <summary>
    /// Controller vibration programming
    /// </summary>
    [Serializable]
    public class ShockResource : Resource
    {
		[Serializable]
	    public class ShockCommand
	    {
		    public ushort TimeOffset;
		    public byte MotorId;
		    public byte ActuatorValue;

		    public ShockCommand(BinaryReader reader)
		    {
			    TimeOffset = reader.ReadUInt16BigEndian();
			    MotorId = reader.ReadByte();
				ActuatorValue = reader.ReadByte();
		    }
	    }

	    public uint NameHash;
	    public short Version;
	    public short CommandCount;
	    public ShockCommand[] ShockCommands;

	    public ShockResource(byte[] data)
	    {
		    var stream = new MemoryStream(data);
		    var reader = new BinaryReader(stream);

			NameHash = reader.ReadUInt32BigEndian();
		    Version = reader.ReadInt16BigEndian();
			CommandCount = reader.ReadInt16BigEndian();

			reader.ReadBytes(4); // runtime memory address of array

			ShockCommands = new ShockCommand[CommandCount];
			for (var i = 0; i < CommandCount; i++)
			{
				ShockCommands[i] = new ShockCommand(reader);
			}

			reader.Dispose();
			stream.Dispose();
		}
    }
}

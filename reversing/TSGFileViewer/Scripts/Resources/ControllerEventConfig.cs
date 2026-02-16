using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

namespace Assets.Scripts.Resources
{
	[Flags]
	public enum PadInputs
	{
		Left_DPadUp = 1,
		Left_DPadDown = 2,
		Left_DPadLeft = 4,
		Left_DpadRight = 8,
		Right_DPadUp = 0x10,	// PS3 Triangle	360 Y
		Right_DPadDown = 0x20,	// PS3 Cross	360 A
		Right_DPadLeft = 0x40,	// PS3 Square	360 X
		Right_DpadRight = 0x80, // PS3 Circle	360 B
		LeftShoulderTop = 0x100,
		LeftShoulderBottom = 0x200,
		RightShoulderTop = 0x400,
		RightShoulderBottom = 0x800,
		Start = 0x1000,
		Select = 0x2000,
		LeftStick = 0x4000,
		RightStick = 0x8000
	}

    [Serializable]
    public class ControllerEventConfig : Resource
    {
		[Serializable]
	    public class CtrlEventDesc
	    {
		    public uint EventHashId; // SDBM hash
		    public byte SequenceLength;
		    public string EventName; // char[26]
		    public string EventCategory; // char[13]
		    public PadPattern[] Sequence = new PadPattern[7];

		    public CtrlEventDesc(BinaryReader reader)
		    {
			    EventHashId = reader.ReadUInt32BigEndian();
				Debug.Log($"- EventHashId: {EventHashId:X8}");
			    SequenceLength = reader.ReadByte();
			    EventName = reader.ReadStringBytes(26);
				EventCategory = reader.ReadStringBytes(13);

				for (var i = 0; i < 7; i++)
				{
					Sequence[i] = new PadPattern(reader);
				}
		    }
	    }

	    [Serializable]
		public class PadPattern
	    {
			public byte[] sticksMin = new byte[2];
			public byte[] sticksMax = new byte[2];
			public short minDurationInMs;
			public short maxDurationInMs;
			public PadInputs buttonRequired;
			public PadInputs buttonDiscarded;

			public PadPattern(BinaryReader reader)
			{
				sticksMin[0] = reader.ReadByte();
				sticksMin[1] = reader.ReadByte();
				sticksMax[0] = reader.ReadByte();
				sticksMax[1] = reader.ReadByte();
				minDurationInMs = reader.ReadInt16BigEndian();
				maxDurationInMs = reader.ReadInt16BigEndian();
				buttonRequired = (PadInputs)reader.ReadUInt16BigEndian();
				buttonDiscarded = (PadInputs)reader.ReadUInt16BigEndian();
			}
	    }

	    public byte EventConfigVersion;
	    public short EventConfigSize;
	    public uint ConfigNameHash; // SDBM hash
	    public byte ReferenceCount;
	    public string ConfigName; // char[33]
	    public string ConfigFileLocation; // char[143]
	    public CtrlEventDesc[] EventDescs;

	    public ControllerEventConfig(byte[] data)
	    {
		    var stream = new MemoryStream(data);
		    var reader = new BinaryReader(stream);

			EventConfigVersion = reader.ReadByte();
			reader.ReadByte(); // padding
			EventConfigSize = reader.ReadInt16BigEndian();
			ConfigNameHash = reader.ReadUInt32BigEndian();
			ReferenceCount = reader.ReadByte();
			ConfigName = reader.ReadStringBytes(33);
			Debug.Log($"ConfigName: {ConfigName}");
			ConfigFileLocation = reader.ReadStringBytes(143);
			Debug.Log($"ConfigFileLocation: {ConfigFileLocation}");

			// 3 bytes of padding
			// 4 byte pointer to CtrlEventDesc array - value from file overwritten when loading to actual memory address

			reader.BaseStream.Position = 0xC0;

			EventDescs = new CtrlEventDesc[EventConfigSize];
			for (var i = 0; i < EventConfigSize; i++)
			{
				EventDescs[i] = new CtrlEventDesc(reader);
			}

			reader.Dispose();
			stream.Dispose();
	    }
    }
}

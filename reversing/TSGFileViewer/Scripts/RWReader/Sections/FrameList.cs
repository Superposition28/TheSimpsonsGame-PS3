using RWReader.RWStructs;
using System;
using System.IO;
using System.Numerics;

namespace RWReader.Sections
{
	public class FrameList : Section
	{
		public FrameList()
		{
			Name = "Frame List";
			Header.ClumpID = 0x0000000E;
			DataStorageType = SectionDataStorage.DataInStruct;
			CanHaveChildren = true;
		}

		public int FrameCount;
		public Frame[] Frames;

		public override void Deserialize(BinaryReader reader)
		{
			FrameCount = reader.ReadInt32();

			Frames = new Frame[FrameCount];

			for (var i = 0; i < FrameCount; i++)
			{
				var frame = new Frame();

				var right = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
				var up = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
				var at = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());

				frame.RotationMatrix = new Matrix3x3(right, up, at);
				frame.Position = new Vector3(reader.ReadSingle(), reader.ReadSingle(), reader.ReadSingle());
				frame.ParentFrame = reader.ReadInt32();
				frame.MatrixFlags = reader.ReadInt32();
				Frames[i] = frame;
			}
		}
	}
}
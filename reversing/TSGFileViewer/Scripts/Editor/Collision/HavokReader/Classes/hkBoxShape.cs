using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkBoxShape : hkConvexShape
	{
		public hkBoxShape()
		{
			Name = "hkBoxShape";
		}

		public float X;
		public float Y;
		public float Z;
		public float W;

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);
			X = reader.ReadSingleBigEndian();
			Y = reader.ReadSingleBigEndian();
			Z = reader.ReadSingleBigEndian();
			W = reader.ReadSingleBigEndian();

			return null;
		}
	}
}

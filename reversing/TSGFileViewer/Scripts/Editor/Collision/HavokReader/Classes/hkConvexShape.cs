using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkConvexShape : hkShape
	{
		public hkConvexShape()
		{
			Name = "hkConvexShape";
		}

		public float ConvexRadius;

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);
			ConvexRadius = reader.ReadSingleBigEndian();
			return null;
		}
	}
}

using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkShape : hkReferencedObject
	{
		public hkShape()
		{
			Name = "hkShape";
		}

		public ulong UserData;

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);
			UserData = reader.ReadUInt64BigEndian();
			return null;
		}
	}
}

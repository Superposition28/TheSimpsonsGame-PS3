using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class UnknownClass : HavokClass
	{
		public UnknownClass()
		{
			Name = "Unknown";
		}

		public override Mesh Deserialize(BinaryReader reader)
		{
			return null;
		}
	}
}

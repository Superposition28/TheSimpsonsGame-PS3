using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader
{
	public abstract class HavokClass
	{
		public string Name;

		public abstract Mesh Deserialize(BinaryReader reader);
	}
}

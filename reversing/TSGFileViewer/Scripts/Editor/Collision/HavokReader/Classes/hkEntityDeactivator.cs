using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader.Classes
{
	public class hkEntityDeactivator : hkReferencedObject
	{
		public hkEntityDeactivator()
		{
			Name = "hkEntityDeactivator";
		}

		public override Mesh Deserialize(BinaryReader reader)
		{
			base.Deserialize(reader);
			return null;
		}
	}
}
	
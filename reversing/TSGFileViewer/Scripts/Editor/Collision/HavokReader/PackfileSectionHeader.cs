using System.IO;
using UnityEngine;

namespace Editor.Collision.HavokReader
{
	public class PackfileSectionHeader
	{
		public string SectionTag;
		public int AbsoluteDataStart;
		public int LocalFixupsOffset;
		public int GlobalFixupsOffset;
		public int VirtualFixupsOffset;
		public int ExportsOffset;
		public int ImportsOffset;
		public int EndOffset;

		public void Deserialize(BinaryReader reader)
		{
			SectionTag = System.Text.Encoding.UTF8.GetString(reader.ReadBytes(19));
			SectionTag = SectionTag.TrimEnd('\0');
			Debug.Log($"(SectionTag={SectionTag})");
			reader.ReadByte(); // null byte
			AbsoluteDataStart = reader.ReadInt32BigEndian();
			LocalFixupsOffset = reader.ReadInt32BigEndian();
			GlobalFixupsOffset = reader.ReadInt32BigEndian();
			VirtualFixupsOffset = reader.ReadInt32BigEndian();
			ExportsOffset = reader.ReadInt32BigEndian();
			ImportsOffset = reader.ReadInt32BigEndian();
			EndOffset = reader.ReadInt32BigEndian();
			Debug.Log("(done!)");
		}

		public int GetDataSize() => LocalFixupsOffset;
		public int GetLocalSize() => GlobalFixupsOffset - LocalFixupsOffset;
		public int GetGlobalSize() => VirtualFixupsOffset - GlobalFixupsOffset;
		public int GetFinishSize() => ExportsOffset - VirtualFixupsOffset;
		public int GetExportsSize() => ImportsOffset - ExportsOffset;
		public int GetImportsSize() => EndOffset - ImportsOffset;
	}
}

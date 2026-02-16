using System.IO;

namespace Editor.Collision.HavokReader
{
	public class PackfileHeader
	{
		public int UserTag;
		public int FileVersion;
		public byte LayoutRules_BytesInPointer;
		public bool LayoutRules_LittleEndian;
		public bool LayoutRules_ReusePaddingOptimization;
		public bool LayoutRules_EmptyBaseClassOptimization;
		public int NumSections;
		public int ContentsSectionIndex;
		public int ContentsSectionOffset;
		public int ContentsClassNameSectionIndex;
		public int ContentsClassNameSectionOffset;
		public string ContentsVersion;

		public void Deserialize(BinaryReader reader)
		{
			var magic0 = reader.ReadInt32BigEndian();
			var magic1 = reader.ReadInt32BigEndian();

			UserTag = reader.ReadInt32BigEndian();
			FileVersion = reader.ReadInt32BigEndian();

			LayoutRules_BytesInPointer = reader.ReadByte();
			LayoutRules_LittleEndian = reader.ReadBoolean();
			LayoutRules_ReusePaddingOptimization = reader.ReadBoolean();
			LayoutRules_EmptyBaseClassOptimization = reader.ReadBoolean();

			NumSections = reader.ReadInt32BigEndian();
			ContentsSectionIndex = reader.ReadInt32BigEndian();
			ContentsSectionOffset = reader.ReadInt32BigEndian();
			ContentsClassNameSectionIndex = reader.ReadInt32BigEndian();
			ContentsClassNameSectionOffset = reader.ReadInt32BigEndian();
			ContentsVersion = System.Text.Encoding.UTF8.GetString(reader.ReadBytes(16));

			// padding
			reader.ReadInt32BigEndian();
			reader.ReadInt32BigEndian();
		}
	}
}

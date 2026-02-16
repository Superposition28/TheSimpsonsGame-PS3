using System;
using System.IO;
using System.Linq;

namespace RWReader
{
	public class RWStreamReader
	{
		private SectionManager SectionManager = new();

		public Section Read(string filepath)
		{
			var stream = new MemoryStream(File.ReadAllBytes(filepath));
			var reader = new BinaryReader(stream);
			var section = ReadSection(reader, null);

			reader.Dispose();
			stream.Dispose();

			return section;
		}

		public Section Read(byte[] data)
		{
			var stream = new MemoryStream(data);
			var reader = new BinaryReader(stream);
			var section = ReadSection(reader, null);

			reader.Dispose();
			stream.Dispose();

			return section;
		}

		public SectionHeader ReadHeader(BinaryReader reader)
		{
			var header = new SectionHeader
			{
				ClumpID = reader.ReadInt32(),
				Size = reader.ReadInt32(),
				LibraryID = new LibraryID(reader.ReadInt32())
			};

			return header;
		}

		public Section ReadSection(BinaryReader reader, Section parent)
		{
			var header = ReadHeader(reader);

			var data = reader.ReadBytes(header.Size);
			var newStream = new MemoryStream(data);
			var newReader = new BinaryReader(newStream);

			var section = SectionManager.GetSection(header);
			section.Raw = data;
			section.Parent = parent;

			var parentCount = 0;
			var currentParent = parent;
			while (currentParent != null)
			{
				parentCount++;
				currentParent = currentParent.Parent;
			}

			//Debug.Log($"{string.Join("", Enumerable.Repeat("-", parentCount))}Read {section.Name} ({header.ClumpID:X8})");
			Console.WriteLine($"{string.Join("", Enumerable.Repeat("-", parentCount))}Read {section.Name}");

			if (section.DataStorageType == SectionDataStorage.DataInSection)
			{
				section.Deserialize(newReader);
			}
			else if (section.DataStorageType == SectionDataStorage.DataInStruct)
			{
				var structSection = ReadSection(newReader, section);
				section.Children.Add(structSection);

				var structStream = new MemoryStream(structSection.Raw);
				var structReader = new BinaryReader(structStream);

				section.Deserialize(structReader);

				structReader.Dispose();
				structStream.Dispose();
			}

			if (newReader.BaseStream.Position == header.Size || !section.CanHaveChildren)
			{
				return section;
			}

			while (newReader.BaseStream.Position != header.Size)
			{
				var childSection = ReadSection(newReader, section);
				section.Children.Add(childSection);
			}

			newReader.Dispose();
			newReader.Dispose();

			return section;
		}
	}
}
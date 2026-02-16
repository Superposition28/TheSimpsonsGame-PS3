using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using static Codice.Client.Common.EventTracking.TrackFeatureUseEvent.Features.DesktopGUI;

namespace Editor.Collision.HavokReader
{
	public class HavokBinaryReader
	{
		public Packfile Read(string filepath)
		{
			var bytes = File.ReadAllBytes(filepath);
			var stream = new MemoryStream(bytes);
			var reader = new BinaryReader(stream);

			var tstMagic = reader.ReadInt32BigEndian();
			if (tstMagic == 1215002640)
			{
				reader.Dispose();
				stream.Dispose();

				stream = new(bytes.Skip(16).ToArray());
				reader = new(stream);
			}

			var packfile = new Packfile();

			packfile.Header = new();
			packfile.Header.Deserialize(reader);

			Debug.Log($"FILE VERSION: {packfile.Header.FileVersion}, {packfile.Header.ContentsVersion}");

			packfile.SectionHeaders = new PackfileSectionHeader[packfile.Header.NumSections];
			for (var i = 0; i < packfile.Header.NumSections; i++)
			{
				var sectionHeader = new PackfileSectionHeader();
				sectionHeader.Deserialize(reader);
				packfile.SectionHeaders[i] = sectionHeader;
			}

			var dataHeader = packfile.SectionHeaders.First(x => x.SectionTag == "__data__");

			// Get mapping between classes
			reader.BaseStream.Position = dataHeader.AbsoluteDataStart + dataHeader.VirtualFixupsOffset;

			var ptrMapping = new List<(int dataOffset, int classnameOffset)>();
			while (true)
			{
				var dataOffset = reader.ReadInt32BigEndian();
				if (dataOffset == -1)
				{
					break;
				}

				reader.ReadInt32BigEndian(); // unknown
				var classnameOffset = reader.ReadInt32BigEndian();
				ptrMapping.Add((dataOffset, classnameOffset));

				if (reader.BaseStream.Position == reader.BaseStream.Length)
				{
					break;
				}
			}

			var nameMapping = new List<(int dataOffset, string className)>();
			var classnameHeader = packfile.SectionHeaders.First(x => x.SectionTag == "__classnames__");
			foreach (var item in ptrMapping)
			{
				reader.BaseStream.Position = classnameHeader.AbsoluteDataStart + item.classnameOffset;
				var classname = reader.ReadNullTerminatedString();
				nameMapping.Add((item.dataOffset, classname));
			}

			foreach (var item in nameMapping)
			{
				reader.BaseStream.Position = dataHeader.AbsoluteDataStart + item.dataOffset;
				Debug.Log($"{item.className} at {reader.BaseStream.Position}");
				var c = ClassManager.GetClass(item.className);
				var mesh = c.Deserialize(reader);

				if (mesh != null)
				{
					var meshObj = new GameObject(mesh.name);
					var mf = meshObj.AddComponent<MeshFilter>();
					mf.sharedMesh = mesh;
					meshObj.AddComponent<MeshCollider>();
					meshObj.transform.localScale = new Vector3(-1, 1, 1);
					meshObj.transform.localPosition = Vector3.zero;

				}
			}

			reader.Dispose();
			stream.Dispose();

			return packfile;
		}
	}
}

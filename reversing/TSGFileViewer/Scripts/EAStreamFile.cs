using Assets.Scripts.ResourceHandlers;
using Assets.Scripts.Resources;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using static UnityEditor.Progress;

public class EAStreamFile {
	// struct __cppobj EARS::Framework::StreamFile
	public struct StreamFile {
		public Guid32 Guid;
		public string FileName;
		public byte nParents;
		public byte nForceLoad;
		public byte nSections;
		public byte Flags;
		public int pRelatives;
		public int pSectionInfo;
	}

	public class StreamSection {
		public string strFilePath;

		public uint memPolicyID;
		public uint compressorID;
		public int dataSize;
		public int allocSize;
		public int readSize;
		public int readOffset;
	}

	static StreamFile ReadStreamFile(BinaryReader reader, int pointerOffset)
	{
		var streamFile = new StreamFile();

		streamFile.Guid = new((uint)reader.ReadInt32BigEndian());                       // m_guid32
		streamFile.FileName = reader.ReadNullTerminatedStringAtPointer(pointerOffset);  // m_pFileName
		streamFile.nParents = reader.ReadByte();                                        // m_nParents
		streamFile.nForceLoad = reader.ReadByte();                                      // m_nForceLoad
		streamFile.nSections = reader.ReadByte();                                       // m_nSections
		streamFile.Flags = reader.ReadByte();                                           // m_flags
		reader.ReadInt32BigEndian();
		streamFile.pRelatives = reader.ReadInt32BigEndian();                            // m_pRelatives
		streamFile.pSectionInfo = reader.ReadInt32BigEndian();                          // m_pSectionInfo

		return streamFile;
	}

	public static void LoadSTRFile(string usrdirPath, string filePath)
	{
		var actualFilePath = Path.Join(usrdirPath, filePath) + ".str";

		if (!File.Exists(actualFilePath))
		{
			Debug.LogError($"{actualFilePath} doesn't exist!");
			return;
		}

		Debug.Log($"Loading {actualFilePath}");
		var stream = new MemoryStream(File.ReadAllBytes(actualFilePath));
		var reader = new BinaryReader(stream);

		// --- EARS::Framework::StreamHeader ---
		reader.ReadBytes(4); // SToc magic				// magicNumber
		var version = reader.ReadInt32BigEndian();      // version
		var nSections = reader.ReadByte();              // nSections
		var platformID = reader.ReadByte();             // platformID
		reader.ReadBytes(2); // padding					// pad1, pad2
		var pStreamFile = reader.ReadInt32BigEndian();  // pStreamFile
		var pSectionArr = reader.ReadInt32BigEndian();  // pSectionArr

		var strFileObj = new GameObject(filePath + ".str");

		reader.BaseStream.Position = pStreamFile;

		if (pStreamFile != 0)
		{
			var streamFile = ReadStreamFile(reader, pStreamFile);

			/*for (var i = 0; i < streamFile.nParents; i++)
				{
					reader.BaseStream.Position = pStreamFile + streamFile.pRelatives + (i * 4);
					var relativeOffset = reader.ReadInt32BigEndian();
					reader.BaseStream.Position = pStreamFile + relativeOffset;
					var newStreamFile = ReadStreamFile(reader, pStreamFile);
				}*/

			if (streamFile.nParents > 1)
			{
				throw new NotImplementedException("More than 1 parent!");
			}

			if (streamFile.nParents != 0)
			{
				reader.BaseStream.Position = pStreamFile + streamFile.pRelatives;
				var relativeOffset = reader.ReadInt32BigEndian();
				reader.BaseStream.Position = pStreamFile + relativeOffset;
				var newStreamFile = ReadStreamFile(reader, pStreamFile);

				// Path is weird here. For example the base streamfile could be frontend\frontend,
				// but its parent is frontend_global - even though they're in the same folder.

				var containingFolder = new DirectoryInfo(Path.GetDirectoryName(actualFilePath)).Name;

				LoadSTRFile(usrdirPath, containingFolder + "\\" + newStreamFile.FileName);
			}
		}

		reader.BaseStream.Position = pSectionArr;

		//Debug.Log($"{nSections} sections.");

		var sections = new StreamSection[nSections];

		for (var i = 0; i < nSections; i++)
		{
			var section = new StreamSection
			{
				strFilePath = filePath,
				memPolicyID = reader.ReadUInt32BigEndian(),
				compressorID = reader.ReadUInt32BigEndian(),
				dataSize = reader.ReadInt32BigEndian(),
				allocSize = reader.ReadInt32BigEndian(),
				readSize = reader.ReadInt32BigEndian(),
				readOffset = reader.ReadInt32BigEndian()
			};
			sections[i] = section;
		}

		var dataStart = 20 + (nSections * 24);
		dataStart = (dataStart + (0x800 - 1)) & -(0x800);

		reader.BaseStream.Position = dataStart;

		for (var i = 0; i < nSections; i++)
		{
			//Debug.Log($"SECTION {i + 1}:");
			var section = sections[i];
			ReadSection(reader, section, strFileObj);
		}

		Debug.Log($"Done reading {actualFilePath}!");
	}

	public static void ReadSection(BinaryReader reader, StreamSection section, GameObject strFileObj)
	{
		//Console.WriteLine($"Reading section at {reader.BaseStream.Position:x8}");
		var chunkStart = reader.BaseStream.Position;

		BinaryReader actualReader;

		if (section.compressorID == 0xB9F0B9EC) // refpack
		{
			var bytes = reader.ReadBytes(section.readSize);
			var decompressed = Refpack.Decompress(bytes);
			actualReader = new BinaryReader(new MemoryStream(decompressed));
		}
		else if (section.compressorID == 0x0EAC15C8) // normal
		{
			actualReader = reader;
		}
		else
		{
			throw new NotImplementedException();
		}

		var readAnotherChunk = true;
		var chunkIndex = 0;
		while (readAnotherChunk)
		{
			//Debug.Log($"CHUNK {chunkIndex + 1}:");
			ReadChunk(actualReader, section, strFileObj);
			chunkIndex++;

			if (actualReader.BaseStream.Position == actualReader.BaseStream.Length)
			{
				break;
			}

			var checkBytes = actualReader.ReadBytes(2);
			actualReader.BaseStream.Position -= 2;
			readAnotherChunk = checkBytes[0] != 0 || checkBytes[1] != 0;

			if (actualReader.BaseStream.Position == chunkStart + section.readSize)
			{
				readAnotherChunk = false;
			}
		}

		if (section.compressorID == 0x0EAC15C8) // normal
		{
			actualReader.BaseStream.Position += (section.readSize - section.dataSize);
		}

		//Console.WriteLine("Done reading section!");
	}

	public static void ReadChunk(BinaryReader reader, StreamSection section, GameObject strFileObj)
	{
		//Console.WriteLine($"Reading chunk at {reader.BaseStream.Position:x8}");
		var chunkType = reader.ReadUInt16BigEndian();
		//reader.BaseStream.Position -= 2;

		if (chunkType == 0x10FB) // refpack
		{
			reader.BaseStream.Position -= 2;
			var bytes = reader.ReadBytes(section.readSize);
			var decompressed = Refpack.Decompress(bytes);
			var decompressedReader = new BinaryReader(new MemoryStream(decompressed));
			ReadChunk(decompressedReader, section, strFileObj);
			decompressedReader.Dispose();
		}

		if (chunkType == 0x1607) // Embedded Asset
		{
			reader.ReadBytes(2); // padding
			var fileSize = reader.ReadInt32(); // little endian
			reader.ReadBytes(4);
			var fileStart = reader.BaseStream.Position;
			var headerSize = reader.ReadInt32BigEndian();

			if (headerSize == 0)
			{
				Console.WriteLine("(Not compressed, no header!)");
			}
			else
			{
				var fileName = reader.ReadRWString();
				//Debug.Log($" - Filename: {fileName}");
				var guid = new Guid128(reader);
				var resourceTypeName = reader.ReadRWString();
				//Debug.Log($" - Resource Type: {resourceTypeName}");
				var fullPath = reader.ReadRWString();
				//Debug.Log($" - Path: {fullPath}");
				reader.ReadBytes(12);
				var size = reader.ReadInt32BigEndian();
				//Debug.Log($" - Size: {size} (position now {reader.BaseStream.Position:X8})");
				reader.Align(16);
				var fileBytes = reader.ReadBytes(size);

				if (ResourceHandlerManager.HandlerExists(resourceTypeName))
				{
					var handler = ResourceHandlerManager.GetHandler(resourceTypeName);
					handler.HandleBytes(fileBytes, guid, section.strFilePath);
				}
				else
				{
					Debug.LogWarning($"No handler found for {resourceTypeName} ({new SDBMHash(resourceTypeName).Value:X8}) at path {(fullPath)}");
				}
			}

			reader.BaseStream.Position = fileStart + fileSize;
		}
		else if (chunkType == 0x2307) // Embedded Asset (Compact)
		{
			throw new NotImplementedException();
		}
		else if (chunkType == 0x2207) // SimGroup
		{
			//Debug.Log("(SimGroup)");

			reader.ReadBytes(2); // padding
			var fileSize = reader.ReadInt32(); // little endian
			reader.ReadBytes(4);

			var bytes = reader.ReadBytes(fileSize);
			SimGroup.LoadSimGroup(bytes, section.strFilePath, strFileObj);
		}
		else
		{
			throw new NotImplementedException();
		}
	}
}
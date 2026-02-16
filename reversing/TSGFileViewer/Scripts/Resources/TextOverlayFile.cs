using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Assets.Scripts.Resources
{
    [Serializable]
    public class TextOverlayFile : Resource
    {
        [Serializable]
	    public class TextOverlayFileHeader
		{
		    public uint ChunkID;
		    public uint FileSizeBytes;
		    public uint Version;
		    public uint NumEntries;

		    public TextOverlayFileHeader(BinaryReader reader)
		    {
			    ChunkID = reader.ReadUInt32BigEndian();
				FileSizeBytes = reader.ReadUInt32BigEndian();
				Version = reader.ReadUInt32BigEndian();
				NumEntries = reader.ReadUInt32BigEndian();
		    }
	    }

	    [Serializable]
		public class TextOverlayFileTextEntry
		{
			public uint HashID;
			public uint StartTimeMS;
			public uint DurationMS;
			public int UserData;

			public TextOverlayFileTextEntry(BinaryReader reader)
			{
				HashID = reader.ReadUInt32BigEndian();
				StartTimeMS = reader.ReadUInt32BigEndian();
				DurationMS = reader.ReadUInt32BigEndian();
				UserData = reader.ReadInt32BigEndian();
			}
		}

	    public TextOverlayFileHeader Header;
	    public TextOverlayFileTextEntry[] Entries;

	    public TextOverlayFile(byte[] data)
	    {
		    var stream = new MemoryStream(data);
		    var reader = new BinaryReader(stream);

		    Header = new TextOverlayFileHeader(reader);

		    Entries = new TextOverlayFileTextEntry[Header.NumEntries];
		    for (var i = 0; i < Header.NumEntries; i++)
		    {
			    Entries[i] = new TextOverlayFileTextEntry(reader);

		    }

		    reader.Dispose();
		    stream.Dispose();
		}
    }
}

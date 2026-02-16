using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Unity.VisualScripting;
using UnityEngine;

namespace Assets.Scripts
{
    public abstract class AttributeHandler : MonoBehaviour
    {
		/// <summary>
		/// The filepath of the .str file this simgroup is contained in.
		/// </summary>
		[NonSerialized]
	    public string STRFile;

	    public abstract void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket);
	}
}
